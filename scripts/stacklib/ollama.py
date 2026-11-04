"""Ollama: environment variables, lifecycle, pulls, benchmark."""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import IS_WINDOWS, info, warn, which


def api(base: str, path: str, payload: dict | None = None, timeout: int = 600) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"}, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def version(base: str) -> str | None:
    try:
        return api(base, "/api/version", timeout=5).get("version")
    except (urllib.error.URLError, OSError, ValueError):
        return None


def set_user_env(env: dict[str, str]) -> list[str]:
    """Persist OLLAMA_* as user environment variables (Windows registry) and in this process.
    Returns the names whose persisted value changed."""
    changed = []
    if IS_WINDOWS:
        import ctypes
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as key:
            for k, v in env.items():
                if not v:
                    continue
                try:
                    cur, _ = winreg.QueryValueEx(key, k)
                except FileNotFoundError:
                    cur = None
                if cur != v:
                    winreg.SetValueEx(key, k, 0, winreg.REG_SZ, v)
                    changed.append(k)
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 0x0002, 5000, None)
    else:
        info("Linux/macOS: set these in the Ollama service environment (systemd: `systemctl edit ollama`):")
        for k, v in env.items():
            if v:
                info(f"  Environment={k}={v}")
    for k, v in env.items():
        if v:
            os.environ[k] = v
    return changed


def stop() -> None:
    """Stop the native Ollama app and server (Windows); systemd's unit on Linux."""
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/IM", "ollama app.exe", "/F"], capture_output=True)
        subprocess.run(["taskkill", "/IM", "ollama.exe", "/F"], capture_output=True)
        time.sleep(1.5)
    else:
        subprocess.run(["systemctl", "stop", "ollama"], capture_output=True)


def restart(base: str) -> None:
    """Restart the native Ollama app so new environment variables apply."""
    if IS_WINDOWS:
        stop()
        app = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama app.exe"
        if app.exists():
            # Launch through Explorer so the tray app becomes a normal desktop process. Started directly, it would
            # stay inside the launching shell's job and die with it (seen when an agent's tool shell exits).
            subprocess.run(["explorer.exe", str(app)], check=False)
        else:
            warn(f"Ollama app not found at {app}; start it from the Start menu")
    else:
        subprocess.run(["systemctl", "restart", "ollama"], capture_output=True)
    for _ in range(30):
        if version(base):
            return
        time.sleep(1)
    warn("Ollama did not come back within 30 s")


def pull(models: list[str]) -> None:
    exe = which("ollama")
    if not exe:
        warn("ollama CLI not found; skipping pulls")
        return
    for m in models:
        if not m:
            continue
        info(f"ollama pull {m}")
        subprocess.run([exe, "pull", m], check=False)


def pull_stream(base: str, model: str, on_progress=None, timeout: float = 300) -> None:
    """Pull one model through the HTTP API, calling on_progress(fraction | None, completed_bytes, total_bytes) as layers
    arrive. Raises RuntimeError with Ollama's message on failure (the CLI only prints it and exits 1)."""
    req = urllib.request.Request(base + "/api/pull", data=json.dumps({"model": model, "stream": True}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    layers: dict[str, tuple[int, int]] = {}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                if not raw.strip():
                    continue
                ev = json.loads(raw)
                if ev.get("error"):
                    raise RuntimeError(ev["error"])
                if ev.get("digest") and ev.get("total"):
                    layers[ev["digest"]] = (ev.get("completed", 0), ev["total"])
                if on_progress:
                    done = sum(c for c, _ in layers.values())
                    total = sum(t for _, t in layers.values())
                    on_progress(done / total if total else None, done, total)
                if ev.get("status") == "success":
                    return
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            body = json.loads(body).get("error", body)
        except ValueError:
            pass
        raise RuntimeError(f"HTTP {e.code}: {body}") from None
    raise RuntimeError("Ollama ended the download without reporting success")


def ps(base: str) -> list[dict]:
    try:
        return api(base, "/api/ps", timeout=10).get("models", [])
    except (urllib.error.URLError, OSError, ValueError):
        return []


def warm(base: str, model: str, num_ctx: int, options: dict | None = None, timeout: float = 900) -> float:
    """Load `model` with no prompt, so the first real request skips the cold load; returns seconds taken.
    num_ctx and options must match the gateway deployment, or that request reloads the runner. No keep_alive is sent:
    OLLAMA_KEEP_ALIVE decides how long the model stays, as it does for gateway requests."""
    t0 = time.time()
    api(base, "/api/generate", {"model": model, "stream": False, "options": {"num_ctx": num_ctx, **(options or {})}}, timeout=timeout)
    return time.time() - t0


def warm_primary(profile: dict, wait: float = 0) -> str:
    """Warm the model behind local-primary (or local-small when there is no primary) and say what happened.
    `wait` is how long to wait for Ollama to answer first, for callers that start before it does (the tray at login)."""
    m = profile["models"]
    model, num_ctx = (m.get("primary"), m["primary_num_ctx"]) if m.get("primary") else (m.get("small"), m.get("small_num_ctx"))
    if not model:
        return "warm-up skipped: no local chat model in this profile"
    base = f"http://127.0.0.1:{profile['ports']['ollama']}"
    deadline = time.time() + wait
    while version(base) is None:
        if time.time() >= deadline:
            return "warm-up skipped: Ollama is not answering"
        time.sleep(5)
    try:
        secs = warm(base, model, num_ctx, m.get("primary_options") if m.get("primary") else None)
    except (urllib.error.URLError, OSError, ValueError) as e:
        return f"warm-up of {model} failed: {e}"
    return f"warmed {model} (num_ctx {num_ctx}) in {secs:.1f} s"


def nvidia_used_mib() -> int | None:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout
        return int(float(out.strip().splitlines()[0]))
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None


BENCH_PROMPT = (
    "Write a Python function `top_k_frequent(words, k)` that returns the k most frequent words, ties broken alphabetically, "
    "with a docstring and two pytest tests. Then explain the time complexity in two sentences."
)


def bench(base: str, model: str, num_ctx: int, num_predict: int = 256, runs: int = 1, options: dict | None = None) -> dict:
    """Load a model, generate, and report tok/s plus the GPU/CPU split reported by /api/ps.
    `options` are extra Ollama request options (e.g. use_mmap) applied on top of num_ctx/num_predict."""
    results = []
    opts = {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": 0.2, **(options or {})}
    for i in range(runs):
        t0 = time.time()
        r = api(
            base,
            "/api/chat",
            {
                "model": model,
                "stream": False,
                "messages": [{"role": "user", "content": BENCH_PROMPT}],
                "options": opts,
                "keep_alive": "10m",
            },
            timeout=1800,
        )
        wall = time.time() - t0
        ev, evd = r.get("eval_count", 0), r.get("eval_duration", 1)
        pe, ped = r.get("prompt_eval_count", 0), r.get("prompt_eval_duration", 1)
        results.append(
            {
                "run": i + 1,
                "wall_s": round(wall, 1),
                "load_s": round(r.get("load_duration", 0) / 1e9, 1),
                "prompt_tokens": pe,
                "prefill_tok_s": round(pe / (ped / 1e9), 1) if ped else None,
                "gen_tokens": ev,
                "decode_tok_s": round(ev / (evd / 1e9), 1) if evd else None,
            }
        )
    loaded = next((x for x in ps(base) if x.get("name") == model or x.get("model") == model), {})
    size, vram = loaded.get("size", 0), loaded.get("size_vram", 0)
    return {
        "model": model,
        "num_ctx": num_ctx,
        "options": {k: v for k, v in opts.items() if k not in ("num_ctx", "num_predict", "temperature")},
        "runs": results,
        "resident_gb": round(size / 1e9, 1) if size else None,
        "resident_vram_gb": round(vram / 1e9, 1) if vram else None,
        "gpu_share_pct": round(100 * vram / size) if size else None,
        "context_length": loaded.get("context_length"),
        "nvidia_smi_used_mib": nvidia_used_mib(),
    }
