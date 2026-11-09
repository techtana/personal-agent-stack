"""Where the stack's disk space goes: every model, program and data folder it keeps, measured on disk.

The tray's Storage card shows this, grouped as Models, Programs and Data, with a total per drive. Measuring walks every
file (an Open WebUI environment has tens of thousands), so the tray scans in a thread of its own, once on opening and
on Refresh, never in the status poll.

Models: Ollama's (from Ollama when it runs, else its manifests), the image models in ComfyUI's models folder, and each
model folder in the Hugging Face cache (Whisper, Kokoro, and any other download, marked as not used by the stack).
Programs: the uv tool environments, this app's own environment, ComfyUI, voice typing, recordings, OpenClaw and
Ollama itself. Data: chats and uploads, traces, logs, the images and recordings made, and download caches.
"""
from __future__ import annotations

import shutil
import time
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path

from . import REPO, TRACES_DIR, features, uninstall, which

GROUPS = ("Models", "Programs", "Data")


@dataclass
class Entry:
    group: str          # one of GROUPS
    name: str           # what it is, for the row
    path: str           # where (a folder or file; the drive comes from it)
    bytes: int = 0
    note: str = ""      # "in use: chat", "not used by the stack", "can be deleted", ...
    level: str = "ok"   # ok | warn | off (muted)


@dataclass
class Scan:
    entries: list[Entry] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)   # what could not be measured, in sentences
    took_s: float = 0.0
    at: float = 0.0      # time.time() when it finished

    def total(self, group: str | None = None) -> int:
        return sum(e.bytes for e in self.entries if group is None or e.group == group)

    def by_drive(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.entries:
            drive = drive_of(e.path)
            out[drive] = out.get(drive, 0) + e.bytes
        return dict(sorted(out.items()))


def drive_of(path: str | Path) -> str:
    """'C:' on Windows, the mount's first folder ('/home') elsewhere; '?' for no path."""
    p = Path(path)
    if p.drive:
        return p.drive.upper()
    parts = p.parts
    return "/" + parts[1] if len(parts) > 1 and p.is_absolute() else "?"


def free_bytes(drive: str) -> int | None:
    root = drive + "\\" if drive.endswith(":") else drive
    try:
        return shutil.disk_usage(root).free
    except OSError:
        return None


def size_text(n: int) -> str:
    if n >= 10 ** 9:
        return f"{n / 1e9:.1f} GB"
    if n >= 10 ** 6:
        return f"{n / 1e6:.0f} MB"
    return f"{n / 1e3:.0f} kB" if n else "0"


MIN_BYTES = 10 ** 6   # leftovers smaller than this (a cache's refs, an empty folder) are not worth a row


def _add(out: list[Entry], group: str, name: str, path, note: str = "", level: str = "ok", size: int | None = None) -> None:
    """Measure `path` and keep the entry when there is something there (data folders count from any size)."""
    if not path:
        return
    p = Path(path)
    if size is None:
        if not p.exists():
            return
        size = uninstall.dir_bytes(p)
    if size >= (1 if group == "Data" else MIN_BYTES):
        out.append(Entry(group, name, str(p), size, note, level))


# ---------------------------------------------------------------- what to measure

def _ollama_models(profile: dict, out: list[Entry]) -> None:
    store = features.effective_model_store(profile)
    for row in uninstall.model_rows(profile):
        if not row.downloaded:
            continue
        note = f"Ollama  ·  in use: {row.use}" if row.use else "Ollama  ·  not used by the stack"
        _add(out, "Models", row.name, store, note, "ok" if row.use else "off", size=int(row.size_gb * 1e9))


def _image_models(profile: dict, out: list[Entry]) -> None:
    from . import media

    m = profile.get("media") or {}
    if not m.get("models_dir"):
        return
    root = Path(m["models_dir"])
    known = 0
    for x in media.MODELS:
        p = root / x.folder / x.name
        if p.exists():
            size = p.stat().st_size
            known += size
            _add(out, "Models", x.name, p, f"image model  ·  {media.WORKFLOW_LABELS.get(x.workflow, x.workflow)}",
                 size=size)
    if root.exists():
        rest = uninstall.dir_bytes(root) - known
        if rest > 50 * 10 ** 6:
            _add(out, "Models", "Other image models", root, "ComfyUI's models folder: added by hand or by ComfyUI",
                 size=rest)


def _hf_models(profile: dict, out: list[Entry], status: dict) -> None:
    from .dictation.models import REPOS
    from .dictation.speak import KOKORO_REPO, ZH_REPO

    home = uninstall.hf_home(profile)
    anchor = Path(home.anchor) if home.anchor else None
    if anchor and not anchor.exists():
        out.append(Entry("Models", "Hugging Face cache", str(home), 0,
                         f"drive {home.drive or anchor} is not connected: Whisper and Kokoro cannot download", "warn"))
        return
    hub = home / "hub"
    if not hub.is_dir():
        return
    whisper = {repo: name for name, repo in REPOS.items() if name != "turbo"}   # "turbo" is large-v3-turbo again
    users = {fid: uninstall.whisper_used(profile, fid) for fid in ("voice_typing", "recordings")
             if uninstall._installed(status, fid)}
    for d in sorted(hub.iterdir()):
        if not d.is_dir() or not d.name.startswith("models--"):
            continue
        repo = d.name.removeprefix("models--").replace("--", "/", 1)
        if repo == KOKORO_REPO:
            name, note, level = "Kokoro-82M", "read aloud's voices and weights", "ok"
        elif repo == ZH_REPO:
            name, note, level = "Kokoro-82M v1.1-zh", "read aloud's Mandarin voices (Remove on the Features card)", "ok"
        elif repo in whisper:
            model = whisper[repo]
            name = f"Whisper {model}"
            who = [features.BY_ID[fid].short for fid, models in users.items() if model in models]
            note, level = (f"used by {' and '.join(who)}", "ok") if who else ("not used now", "off")
        else:
            name, note, level = repo, "Hugging Face  ·  not used by the stack", "off"
        _add(out, "Models", name, d, note, level)
    for sub, what in (("xet", "Hugging Face download cache"),):
        _add(out, "Data", what, home / sub, "can be deleted; downloads fill it again", "off")


def _voices(profile: dict, out: list[Entry]) -> None:
    """Read aloud's Piper voices for more languages, one folder each."""
    from . import dictation
    from .dictation.speak import PIPER_VOICES, language_label

    folder = dictation.packs_dir(profile)
    for key in dictation.installed_packs(profile):
        meta = PIPER_VOICES[key]
        who = " and ".join(str(x[0]) for x in (meta.get("speakers") or {}).values())
        _add(out, "Models", f"{who} ({language_label(str(meta.get('language') or ''))})", folder / key,
             "read aloud voice (Piper)")


def _programs(profile: dict, out: list[Entry]) -> None:
    from . import dictation, services, whisper

    tools = services._uv_tool_dir()
    for env, name in (("litellm", "Gateway (LiteLLM)"), ("open-webui", "Chat in the browser (Open WebUI)"),
                      ("arize-phoenix", "Trace viewer (Phoenix)"), ("huggingface-hub", "hf command")):
        if tools:
            _add(out, "Programs", name, tools / env)
    _add(out, "Programs", "Agent Stack (tray, orchestrator)", REPO / ".venv", "this app's Python environment")
    m = profile.get("media") or {}
    if m.get("comfyui_dir"):
        comfy = Path(m["comfyui_dir"])
        models_dir = Path(m.get("models_dir") or comfy / "models")
        if comfy.exists():
            size = uninstall.dir_bytes(comfy)
            if models_dir.exists() and uninstall._within(models_dir, comfy):
                size -= uninstall.dir_bytes(models_dir)
            _add(out, "Programs", "Image generation (ComfyUI)", comfy, "with its Python environment", size=max(size, 0))
    _add(out, "Programs", "Voice typing (Whisper)", dictation.env_dir(profile) / ".venv", "read aloud's packages too")
    if m.get("whisper_dir"):
        _add(out, "Programs", "Recordings server", whisper.whisper_dir(profile),
             "no longer offered: Remove it on the Features card", "off")
    claw = uninstall._openclaw_dir()
    if claw:
        _add(out, "Programs", "OpenClaw", claw)
    exe = which("ollama")
    if exe:
        _add(out, "Programs", "Ollama", Path(exe).parent)


def _data(profile: dict, out: list[Entry]) -> None:
    data = Path(profile.get("data_dir") or REPO / ".run")
    _add(out, "Data", "Chats, uploads and settings (Open WebUI)", data / "open-webui")
    _add(out, "Data", "Traces (Phoenix)", data / "phoenix")
    _add(out, "Data", "Logs", data / "logs", "can be deleted")
    _add(out, "Data", "Gateway and usage traces", TRACES_DIR)
    m = profile.get("media") or {}
    if m.get("output_dir"):
        _add(out, "Data", "Images and transcripts made", m["output_dir"])
    if m.get("input_dir"):
        _add(out, "Data", "Inputs and recordings", m["input_dir"])
    if m.get("uv_cache"):
        _add(out, "Data", "Download cache (media tools)", m["uv_cache"], "can be deleted; installs download again", "off")


def scan(profile: dict, status: dict | None = None) -> Scan:
    """Measure everything (seconds: it walks every file). A part that fails is named in problems; the rest stays.
    status: features.statuses() when the caller has it (which features use a shared Whisper model)."""
    start = time.monotonic()
    status = features.statuses(profile) if status is None else status
    s = Scan()
    for part, fn in (("Ollama's models", _ollama_models), ("the image models", _image_models),
                     ("the Hugging Face cache", lambda p, out: _hf_models(p, out, status)),
                     ("read aloud's voices", _voices),
                     ("the programs", _programs), ("the data folders", _data)):
        try:
            fn(profile, s.entries)
        except (OSError, ValueError, KeyError, urllib.error.URLError) as e:
            s.problems.append(f"Could not measure {part}: {e}")
    s.took_s = time.monotonic() - start
    s.at = time.time()
    return s
