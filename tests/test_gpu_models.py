"""The tray's GPU card lists every model on the card, not only Ollama's."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from stacklib import gpu_models  # noqa: E402

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
OLLAMA = [{"name": "qwen3.5:9b", "size": 6_166_413_310, "size_vram": 6_166_413_310, "context_length": 32768,
           "expires_at": (NOW + timedelta(minutes=237, seconds=30)).isoformat()}]
WHISPER_READY = {"ok": True, "engine": "ready", "device": "cuda", "model": "large-v3-turbo",
                 "idle_s": 600, "unload_after_min": 30.0}


def test_ollama_only():
    rows = gpu_models.rows(OLLAMA, now=NOW)
    assert [r["by"] for r in rows] == ["Ollama"]
    assert rows[0]["gpu"] == "100%" and rows[0]["unloads"] == "in 237 min" and not rows[0]["estimate"]


def test_whisper_loaded_on_gpu_is_listed():
    rows = gpu_models.rows(OLLAMA, WHISPER_READY, now=NOW)
    w = rows[1]
    assert w["by"] == "Voice typing" and w["name"] == "whisper large-v3-turbo"
    assert w["gpu"] == "100%" and w["estimate"] and abs(w["bytes"] / 2**30 - 1.2) < 0.01
    assert w["unloads"] == "in 20 min"


def test_whisper_not_listed_until_loaded():
    for state in ("unloaded", "loading", "failed"):
        assert len(gpu_models.rows(OLLAMA, dict(WHISPER_READY, engine=state), now=NOW)) == 1
    assert len(gpu_models.rows(OLLAMA, None, now=NOW)) == 1


def test_whisper_on_cpu_and_old_health():
    cpu = gpu_models.rows([], dict(WHISPER_READY, device="cpu", model="small"), now=NOW)[0]
    assert cpu["gpu"] == "CPU" and cpu["bytes"] == 0
    old = {"engine": "ready", "device": "cuda", "model": "large-v3-turbo"}   # an app started before idle_s existed
    assert gpu_models.rows([], old, now=NOW)[0]["unloads"] == "-"
    never = gpu_models.rows([], dict(WHISPER_READY, unload_after_min=0), now=NOW)[0]
    assert never["unloads"] == "never"


def test_comfyui_listed_only_while_its_torch_holds_memory():
    held = {"devices": [{"type": "cuda", "torch_vram_total": 9 * 2**30}]}
    rows = gpu_models.rows([], None, held, "Z-Image-Turbo int8", now=NOW)
    assert rows == [{"name": "Z-Image-Turbo int8", "by": "ComfyUI", "bytes": 9 * 2**30, "estimate": False,
                     "gpu": "100%", "context": 0, "unloads": "on Chat"}]
    freed = {"devices": [{"type": "cuda", "torch_vram_total": 0}]}
    assert gpu_models.rows([], None, freed, now=NOW) == []
    assert gpu_models.rows([], None, {"devices": "odd"}, now=NOW) == []
