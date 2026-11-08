"""The processes behind the tray's Services card: each module's own process, and one more row wherever a module runs a
model in a process of its own.

Ollama runs every loaded model in a runner process of its own (llama-server, a child of `ollama serve`), so two models
loaded at once are two processes and two pids. Models that run inside their module's process (voice typing's Whisper,
read aloud's Kokoro inside voice typing, ComfyUI's image models) share that pid and get no row of their own; the GPU
card lists them.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import features

MODEL_LAYER = "application/vnd.ollama.image.model"


def _psutil():
    try:
        import psutil

        return psutil
    except ImportError:   # the tray has it; a bare environment just shows no pids
        return None


def _arg(cmd: list[str], *names: str) -> str:
    """The value after the first of `names` on a command line ("--model <path>" or "--model=<path>")."""
    for i, part in enumerate(cmd):
        for n in names:
            if part == n and i + 1 < len(cmd):
                return cmd[i + 1]
            if part.startswith(n + "="):
                return part.split("=", 1)[1]
    return ""


def model_blob(store: str | Path, model: str) -> str:
    """The file name of a pulled model's weights in Ollama's blobs folder (sha256-<hex>), from its manifest; "" when
    the manifest cannot be read."""
    try:
        manifest = json.loads(features.manifest_path(str(store), model).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    for layer in manifest.get("layers") or []:
        if layer.get("mediaType") == MODEL_LAYER and str(layer.get("digest", "")).startswith("sha256:"):
            return "sha256-" + layer["digest"].split(":", 1)[1]
    return ""


def ollama_tree(loaded: list[dict]) -> dict:
    """{"pid": the `ollama serve` process or None, "runners": [{"pid", "model", "context"}]}. A runner is matched to a
    loaded model (Ollama's /api/ps rows in `loaded`) by the weights file it was started with; one that matches none
    is listed with the file name."""
    ps = _psutil()
    out: dict = {"pid": None, "runners": []}
    if ps is None:
        return out
    server = None
    for proc in ps.process_iter(["pid", "name"]):
        name = (proc.info.get("name") or "").lower()
        if name not in ("ollama.exe", "ollama"):
            continue
        try:
            if "serve" in proc.cmdline()[1:]:
                server = proc
                break
        except (ps.Error, OSError):
            continue
    if server is None:
        return out
    out["pid"] = server.pid
    try:
        children = server.children()
    except (ps.Error, OSError):
        children = []
    blobs: dict[str, str] = {}
    for child in children:
        try:
            cmd = child.cmdline()
        except (ps.Error, OSError):
            continue
        weights = _arg(cmd, "--model", "-m")
        if not weights:
            continue
        path = Path(weights)
        if not blobs:   # the store is the folder above blobs/
            store = path.parent.parent
            for row in loaded or []:
                blob = model_blob(store, str(row.get("name") or ""))
                if blob:
                    blobs[blob] = str(row.get("name"))
        ctx = _arg(cmd, "-c", "--ctx-size")
        out["runners"].append({"pid": child.pid, "model": blobs.get(path.name, path.name[:19]),
                               "context": int(ctx) if ctx.isdigit() else 0})
    return out
