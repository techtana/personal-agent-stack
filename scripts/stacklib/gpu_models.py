"""Every model the stack holds on the GPU, for the tray's GPU card: Ollama's chat and embedding models, voice typing's
Whisper and ComfyUI's image models. Each comes from its own service, because no single place knows them all:

- Ollama: GET /api/ps (exact sizes and the share on the GPU);
- voice typing: GET /health on its control port (model, device, idle time). faster-whisper does not report its
  memory, so the size is the figure measured for that model (features.WHISPER, 1.2 GB for large-v3-turbo). The same
  answer says when read aloud's Kokoro is loaded, on the GPU (1.0 GB measured) or the CPU (no GPU memory), and its
  Mandarin model (0.7 GB measured) and its Thai model (1.0 GB measured) too;
- ComfyUI: GET /system_stats, whose torch_vram_total is the GPU memory ComfyUI's own torch holds (models plus cache).

The recordings server for Claude Desktop runs its own Whisper inside Claude Desktop's process tree and has no port to
ask, so it is not listed.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

from . import catalog

GIB = 2**30
COMFY_MIN_BYTES = 256 * 2**20   # below this ComfyUI holds only its CUDA context, not a model
# GB read aloud's Kokoro holds on the GPU (measured 2026-11-08 on an RTX 3060; config/installer.yaml kokoro.gpu_vram_gb)
KOKORO_GPU = float(catalog.kokoro().get("gpu_vram_gb") or 1.0)
# and its Mandarin model, Kokoro v1.1-zh (config/installer.yaml kokoro_zh.gpu_vram_gb), and its Thai model (kokoro_th)
KOKORO_ZH_GPU = float(catalog.section("kokoro_zh").get("gpu_vram_gb") or 0.7)
KOKORO_TH_GPU = float(catalog.section("kokoro_th").get("gpu_vram_gb") or 1.0)


def _unloads_ollama(expires_at: str | None, now: datetime) -> str:
    try:
        left = (datetime.fromisoformat(str(expires_at)) - now).total_seconds()
    except (ValueError, TypeError):
        return "-"
    return "never" if left > 86400 * 365 else (f"in {int(left // 60)} min" if left > 0 else "soon")


def _unloads_after(health: dict) -> str:
    """When a model the voice typing app holds is freed: its unload_after_min against its idle seconds."""
    after, idle = health.get("unload_after_min"), health.get("idle_s")
    if not isinstance(after, (int, float)) or not isinstance(idle, (int, float)):
        return "-"
    if after <= 0:
        return "never"
    left = after * 60 - idle
    return f"in {int(left // 60)} min" if left > 60 else "soon"


def _ollama_rows(rows: list[dict], now: datetime) -> list[dict]:
    out = []
    for m in rows or []:
        size, vram = int(m.get("size") or 0), int(m.get("size_vram") or 0)
        out.append({"name": m.get("name", "?"), "by": "Ollama", "bytes": size, "estimate": False,
                    "gpu": f"{100 * vram / size:.0f}%" if size else "-",
                    "context": int(m.get("context_length") or 0),
                    "unloads": _unloads_ollama(m.get("expires_at"), now)})
    return out


def _whisper_row(health: dict | None) -> dict | None:
    """Voice typing's Whisper while it is loaded; None while it waits for the first dictation or after it unloaded."""
    if not isinstance(health, dict) or health.get("engine") != "ready":
        return None
    from .dictation.models import SPEECH, speech_model

    model = str(health.get("model") or "")
    on_gpu = health.get("device") in ("cuda", "vulkan")   # vulkan: Canary-Qwen through transcribe.cpp
    m = SPEECH.get(model) or speech_model(model or "large-v3-turbo")
    gb = (m.vram_gb or SPEECH["large-v3-turbo"].vram_gb) if on_gpu else 0.0
    name = (f"whisper {model}" if m.engine == "faster-whisper" else model) if model else "whisper"
    return {"name": name, "by": "Voice typing", "bytes": int(gb * GIB),
            "estimate": True, "gpu": "100%" if on_gpu else "CPU", "context": 0, "unloads": _unloads_after(health)}


def _kokoro_row(health: dict | None) -> dict | None:
    """Read aloud's Kokoro while it is loaded (in system memory: it runs on the CPU)."""
    read = health.get("read_aloud") if isinstance(health, dict) else None
    if not isinstance(read, dict) or read.get("engine") != "ready":
        return None
    on_gpu = read.get("device") == "cuda"
    return {"name": str(read.get("model") or "kokoro-82m"), "by": "Read aloud", "bytes": int(KOKORO_GPU * GIB) if on_gpu else 0,
            "estimate": True, "gpu": "100%" if on_gpu else "CPU", "context": 0, "unloads": _unloads_after(read)}


def _kokoro_set_row(health: dict | None, lang: str, default_name: str, gpu_gb: float) -> dict | None:
    """One of read aloud's other Kokoro models (Mandarin under "zh", Thai under "th") while it is loaded; it unloads
    after the same idle minutes."""
    read = health.get("read_aloud") if isinstance(health, dict) else None
    model = read.get(lang) if isinstance(read, dict) else None
    if not isinstance(model, dict) or model.get("engine") != "ready":
        return None
    on_gpu = model.get("device") == "cuda"
    return {"name": str(model.get("model") or default_name), "by": "Read aloud",
            "bytes": int(gpu_gb * GIB) if on_gpu else 0, "estimate": True, "gpu": "100%" if on_gpu else "CPU",
            "context": 0, "unloads": _unloads_after({**model, "unload_after_min": read.get("unload_after_min")})}


def _kokoro_zh_row(health: dict | None) -> dict | None:
    return _kokoro_set_row(health, "zh", "kokoro-82m-v1.1-zh", KOKORO_ZH_GPU)


def _kokoro_th_row(health: dict | None) -> dict | None:
    return _kokoro_set_row(health, "th", "wayu-kokoro-thai-v1", KOKORO_TH_GPU)


def _comfy_row(stats: dict | None, label: str = "") -> dict | None:
    """ComfyUI's models while its torch holds GPU memory; None when it holds only its CUDA context."""
    if not isinstance(stats, dict):
        return None
    held = 0
    for d in stats.get("devices") or []:
        if isinstance(d, dict) and str(d.get("type", "cuda")) == "cuda":
            held += int(d.get("torch_vram_total") or 0)
    if held < COMFY_MIN_BYTES:
        return None
    return {"name": label or "image models", "by": "ComfyUI", "bytes": held, "estimate": False, "gpu": "100%",
            "context": 0, "unloads": "on Chat"}


def rows(ollama_ps: list[dict], dictation_health: dict | None = None, comfy_stats: dict | None = None,
         comfy_label: str = "", now: datetime | None = None) -> list[dict]:
    """One row per model held in memory, Ollama's first. Each row: name, by (who holds it), bytes, estimate (True when
    bytes is a measured figure for the model rather than read now), gpu ("100%", "62%", "CPU"), context (tokens, 0 for
    none) and unloads ("in 12 min", "never", "on Chat", "-")."""
    out = _ollama_rows(ollama_ps, now or datetime.now(timezone.utc))
    for extra in (_whisper_row(dictation_health), _kokoro_row(dictation_health), _kokoro_zh_row(dictation_health),
                  _kokoro_th_row(dictation_health), _comfy_row(comfy_stats, comfy_label)):
        if extra:
            out.append(extra)
    return out


def comfy_stats(port: int, timeout: float = 1.5) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/system_stats", timeout=timeout) as r:
            return json.load(r)
    except (OSError, ValueError, urllib.error.URLError):
        return None
