"""Remove a feature or an Ollama model from this PC: the other half of the installer (stacklib/install.py).

plan() says what a removal deletes and what it keeps, with sizes, for the confirmation in the tray and the installer,
and checks every folder it would delete before anything changes; remove() does it, in the setup worker (install.py runs
it as a step, so the installer window shows its progress too). remove() plans again, refuses when that plan is
blocked, then turns the feature off the way the tray's Settings tab does (settings.apply: stops the service and
restarts what depends on it), waits until nothing runs from the folders it deletes, and deletes them: downloaded
models first, the program folder that makes the feature read as installed last, so a removal that stops halfway can be
run again.

What the owner made with a feature stays: chats and uploads (Open WebUI), traces (Phoenix), images (ComfyUI's
outputs), transcripts (recordings), OpenClaw's own settings, and every setting in machines/<HOST>.yaml. A removal
whose folder holds one of those (an outputs folder inside ComfyUI's) is refused. A model in the shared Hugging Face
cache goes only when no other installed feature uses it.

Deleting is guarded (_check): a folder goes only when it is the feature's own folder as the profile names it and looks
like it (ComfyUI's main.py, a venv's pyvenv.cfg, the recordings server's script, a hub/models--* folder); it is
neither near a drive root, the home folder nor a folder that holds this app; and a media folder is strictly inside
agent_access.allowed_roots, voice typing's environment inside those or this app's data folder.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path

from . import IS_WINDOWS, REPO, features, info, paths, which

# Features the installer can take off again. The local models and the gateway are what every other feature talks to.
REMOVABLE = ("chat", "tracing", "images", "voice_typing", "read_aloud", "recordings", "openclaw")
# The Settings switch that turns each feature off (setting id, off value as the Settings tab edits it).
SWITCH_SETTING = {"chat": "services.open_webui", "tracing": "observability.phoenix", "images": "services.comfyui",
                  "voice_typing": "services.dictation", "read_aloud": "read_aloud.enabled"}
TOOL_ENV = {"chat": "open-webui", "tracing": "arize-phoenix"}   # uv tool environments (config/installer.yaml)
# Folder kinds that make a feature read as installed: deleted after everything else.
PROGRAM_KINDS = ("comfyui", "venv", "whisper")
STOP_WAIT_S = 15   # how long remove() waits for a stopped program to let go of its files


@dataclass
class Item:
    """One thing a removal deletes. kind says how and what it must look like: comfyui, venv and whisper are program
    folders, hf a model folder in the Hugging Face cache, file one model file, tool a uv tool, npm an npm package,
    packages the read aloud packages in voice typing's environment."""
    what: str
    path: str = ""
    size_gb: float | None = None   # None: not there, or not measured
    kind: str = ""
    media: bool = False            # a media folder: must be strictly inside agent_access.allowed_roots


@dataclass
class Removal:
    fid: str
    title: str
    deletes: list[Item] = field(default_factory=list)
    keeps: list[str] = field(default_factory=list)    # what stays, in sentences
    notes: list[str] = field(default_factory=list)    # what else happens (a restart, a setting that goes back)
    also: list[str] = field(default_factory=list)     # features removed with it (read aloud with voice typing)
    blocked: str = ""                                 # why it cannot be removed now, or ""

    @property
    def size_gb(self) -> float:
        return sum(i.size_gb or 0.0 for i in self.deletes)

    def text(self) -> str:
        """The confirmation's body: what goes (with sizes), what else happens, what stays."""
        lines = []
        if self.deletes:
            lines.append("Deletes:")
            lines += [f"  •  {i.what}" + (f" ({features_gb(i.size_gb)})" if i.size_gb else "")
                      + (f" in {short_path(i.path)}" if i.path else "") for i in self.deletes]
        if self.also:
            lines.append("Also removes " + ", ".join(features.BY_ID[f].short for f in self.also)
                         + ", which runs inside it.")
        lines += self.notes
        if self.keeps:
            lines.append("Keeps:")
            lines += [f"  •  {k}" for k in self.keeps]
        return "\n".join(lines)


def features_gb(gb: float | None) -> str:
    if gb is None:
        return "?"
    return f"{gb:.1f} GB" if gb >= 0.1 else f"{gb * 1000:.0f} MB"


def _home() -> str:
    return str(Path.home()).rstrip("\\/")


def short_path(path: str | Path) -> str:
    """A path for the screen, with the home folder as ~ (shorter, and the account name stays off screenshots)."""
    text, home = str(path), _home()
    if text.lower() == home.lower() or text.lower().startswith(home.lower() + os.sep) \
            or text.lower().startswith(home.lower() + "/"):
        return "~" + text[len(home):]
    return text


def short_text(text: str) -> str:
    """Every path in a sentence with the home folder as ~ (see short_path); a longer name that only starts like the
    home folder (C:\\Users\\ab and C:\\Users\\abc) is left as it is."""
    home = _home()
    if len(home) <= 3:
        return str(text or "")
    return re.sub(re.escape(home) + r"(?![\w.-])", "~", str(text or ""), flags=re.IGNORECASE)


# ---------------------------------------------------------------- sizes and places

def dir_bytes(path: str | Path) -> int:
    """Bytes in a folder (or one file). Links and junctions count as their own size and are not followed: hub
    snapshots link to blobs that are counted once, and a junction loop cannot run forever. Uses os.scandir, whose
    entries carry their size on Windows (from the directory listing), several times faster than a stat per file."""
    p = Path(path)
    try:
        if p.is_file():
            return p.stat().st_size
    except OSError:
        return 0
    total, stack = 0, [str(p)]
    while stack:
        try:
            with os.scandir(stack.pop()) as it:
                for entry in it:
                    try:
                        junction = hasattr(entry, "is_junction") and entry.is_junction()
                        if entry.is_dir(follow_symlinks=False) and not junction:
                            stack.append(entry.path)
                        else:
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
        except OSError:
            pass
    return total


def _gb(path: str | Path) -> float | None:
    return dir_bytes(path) / 1e9 if Path(path).exists() else None


def hf_home(profile: dict) -> Path:
    """The Hugging Face cache the stack's downloads go to: media.hf_home, else HF_HOME as Windows has it saved."""
    from . import clients

    home = (profile.get("media") or {}).get("hf_home") or clients.user_env("HF_HOME")
    return Path(home) if home else Path.home() / ".cache" / "huggingface"


def hf_repo_dir(profile: dict, repo: str) -> Path:
    return hf_home(profile) / "hub" / f"models--{repo.replace('/', '--')}"


def whisper_used(profile: dict, fid: str) -> set[str]:
    """Whisper models a feature downloads: its GPU model and its CPU fallback."""
    if fid == "voice_typing":
        d = profile.get("dictation") or {}
        return {str(d.get("model") or "large-v3-turbo"), str(d.get("cpu_model") or "small")}
    if fid == "recordings":
        m = profile.get("media") or {}
        return {str(m.get("whisper_model") or "large-v3-turbo"), str(m.get("whisper_cpu_model") or "small")}
    return set()


def _whisper_items(profile: dict, fid: str, keep_for: set[str]) -> list[Item]:
    """The Whisper models only this feature uses (keep_for: other features that stay installed)."""
    from .dictation.models import repo_for

    shared = set().union(*(whisper_used(profile, other) for other in keep_for)) if keep_for else set()
    items = []
    for name in sorted(whisper_used(profile, fid) - shared):
        d = hf_repo_dir(profile, repo_for(name))
        if d.exists():
            items.append(Item(f"Whisper model {name}", str(d), _gb(d), "hf"))
    return items


def _kokoro_item(profile: dict) -> Item | None:
    from .dictation.speak import KOKORO_REPO

    d = hf_repo_dir(profile, KOKORO_REPO)
    return Item("Kokoro voices and weights", str(d), _gb(d), "hf") if d.exists() else None


def _tool_dir() -> Path | None:
    from . import services

    return services._uv_tool_dir()


def running_from(folder: str | Path) -> list[int]:
    """Pids of processes whose program lives in `folder` (files there are locked while they run)."""
    try:
        import psutil
    except ImportError:
        return []
    if not folder or not Path(folder).exists():
        return []
    base = os.path.normcase(str(Path(folder).resolve())) + os.sep
    out = []
    for proc in psutil.process_iter(["pid", "exe"]):
        exe = proc.info.get("exe")
        if exe and os.path.normcase(exe).startswith(base):
            out.append(proc.info["pid"])
    return out


def _installed(status: dict, fid: str) -> bool:
    """Installed, turned on (a repair may follow), or not known: a shared model stays for such a feature."""
    s = status.get(fid)
    return bool(s and (s.installed or s.on or s.unknown))


def _within(path: Path, parent: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def _data_dir(profile: dict) -> Path:
    return Path(profile.get("data_dir") or REPO / ".run")


# ---------------------------------------------------------------- what a removal does

def plan(profile: dict, fid: str, status: dict | None = None) -> Removal:
    """What removing `fid` deletes and keeps, measured now, with every folder checked (blocked says why not). Never
    changes anything."""
    status = features.statuses(profile) if status is None else status
    f = features.BY_ID[fid]
    r = Removal(fid, f.title)
    if f.required:
        r.blocked = f"{f.title} is required: every other feature talks to it."
        return r
    if fid not in REMOVABLE:
        r.blocked = f"{f.title} cannot be removed from here."
        return r
    stays = {o for o in REMOVABLE if o != fid and _installed(status, o) and fid not in features.BY_ID[o].requires}
    data = _data_dir(profile)
    m = profile.get("media") or {}
    if fid in TOOL_ENV:
        root = _tool_dir()
        env = root / TOOL_ENV[fid] if root else None
        r.deletes.append(Item(f"{f.short}'s program (uv tool {TOOL_ENV[fid]})", str(env or ""),
                              _gb(env) if env else None, "tool"))
        if fid == "chat":
            r.keeps.append(f"Your chats, uploads and Open WebUI settings in {short_path(data / 'open-webui')}; "
                           "installing it again picks them up.")
        else:
            r.keeps.append(f"The traces Phoenix stored in {short_path(data / 'phoenix')}.")
            r.notes.append("The gateway restarts without its trace export (a few seconds).")
    elif fid == "images":
        from . import media

        if m.get("root"):
            comfy = media.comfyui_dir(profile)
            models_dir = Path(m.get("models_dir") or comfy / "models")
            if not _within(models_dir, comfy):   # a models folder of its own: only the catalog's files go
                for x in media.MODELS:
                    p = models_dir / x.folder / x.name
                    if p.exists():
                        r.deletes.append(Item(x.name, str(p), _gb(p), "file", media=True))
            r.deletes.append(Item("ComfyUI, its Python environment and image models", str(comfy), _gb(comfy),
                                  "comfyui", media=True))
            extra = _comfy_extras(comfy, models_dir)
            if extra:
                r.notes.append("Inside ComfyUI's folder, this also deletes " + "; ".join(extra) + ".")
            r.keeps.append(f"The images you made, in {short_path(m.get('output_dir') or '')}.")
        r.notes.append("Open WebUI's image button is turned off.")
    elif fid == "voice_typing":
        from . import dictation

        venv = dictation.env_dir(profile) / ".venv"
        r.deletes += _whisper_items(profile, fid, stays)
        if _installed(status, "read_aloud") or (profile.get("read_aloud") or {}).get("enabled"):
            r.also.append("read_aloud")
            kokoro = _kokoro_item(profile)
            if kokoro:
                r.deletes.append(kokoro)
        r.deletes.append(Item("The voice typing app's Python environment", str(venv), _gb(venv), "venv",
                              media=bool(m.get("root")) and _within(venv, Path(m["root"]))))
        r.notes.append("Open WebUI's microphone goes back to its own Whisper.")
        r.keeps.append(f"Your voice typing settings in machines/{profile.get('name') or '<HOST>'}.yaml.")
    elif fid == "read_aloud":
        kokoro = _kokoro_item(profile)
        if kokoro:
            r.deletes.append(kokoro)
        r.deletes.append(Item("espeak-ng, comtypes and the GPU libraries in voice typing's environment", kind="packages"))
        r.notes.append("Voice typing restarts (a few seconds).")
        r.keeps.append("Voice typing, and Windows' own voices.")
    elif fid == "recordings":
        from . import whisper

        wdir = whisper.whisper_dir(profile) if m.get("whisper_dir") else None
        if wdir:
            r.deletes += _whisper_items(profile, fid, stays)
            r.deletes.append(Item("The recordings server and its Python environment", str(wdir), _gb(wdir), "whisper",
                                  media=True))
            if wdir.exists() and running_from(wdir):
                r.blocked = ("Claude Desktop is running the Whisper server, so its files are in use. Quit Claude "
                             "Desktop (its tray icon > Quit), then remove recordings.")
        if features.desktop_entry() is not None:
            r.notes.append("Claude Desktop's entry for the server is removed (its config is backed up first).")
        r.keeps.append(f"Your recordings and transcripts in {short_path(m.get('input_dir') or '')} and "
                       f"{short_path(m.get('output_dir') or '')}.")
    elif fid == "openclaw":
        claw = _openclaw_dir()
        r.deletes.append(Item("OpenClaw (npm install -g openclaw)", claw, _gb(claw) if claw else None, "npm"))
        r.keeps.append(f"OpenClaw's settings and sessions in {short_path(Path.home() / '.openclaw')}.")
    if not r.blocked:
        r.blocked = _preflight(profile, r)
    return r


def _comfy_extras(comfy: Path, models_dir: Path) -> list[str]:
    """What the owner may have added inside ComfyUI's folder, which deleting it takes along."""
    from . import media

    out = []
    if models_dir.is_dir() and _within(models_dir, comfy):
        known = sum(dir_bytes(models_dir / x.folder / x.name) for x in media.MODELS)
        rest = dir_bytes(models_dir) - known
        if rest > 10 ** 6:
            out.append(f"{features_gb(rest / 1e9)} of other models in its models folder")
    for sub, what in (("custom_nodes", "its custom nodes"), ("user", "its saved workflows and settings")):
        if (comfy / sub).is_dir() and any((comfy / sub).iterdir()):
            out.append(f"{what} ({sub})")
    return out


def _preflight(profile: dict, r: Removal) -> str:
    """Every check remove() needs before it changes anything; "" when all pass, else why not, in a sentence."""
    m = profile.get("media") or {}
    for item in r.deletes:
        if item.kind in ("comfyui", "venv", "whisper", "hf", "file") and item.path and Path(item.path).exists():
            try:
                _check(item, profile)
            except PermissionError as e:
                return f"Not removed, to be safe: {e}."
            if item.kind in PROGRAM_KINDS:   # data the owner made must not sit inside a folder that goes
                for key, what in (("output_dir", "outputs"), ("input_dir", "inputs"), ("recordings_dir", "recordings"),
                                  ("transcripts_dir", "transcripts"), ("hf_home", "Hugging Face cache")):
                    if m.get(key) and _within(Path(m[key]), Path(item.path)):
                        return (f"Not removed, to be safe: the {what} folder {short_path(m[key])} is inside "
                                f"{short_path(item.path)}, which removing would delete. Move it out first.")
    return ""


def _openclaw_dir() -> str:
    exe = which("openclaw")
    if not exe:
        return ""
    folder = Path(exe).parent / "node_modules" / "openclaw"
    return str(folder) if folder.exists() else ""


def _guard(path: Path, profile: dict, media_folder: bool) -> None:
    """Refuse to delete anything that is not clearly a feature's own folder: nothing near a drive root, nothing that
    holds the home folder or this app, nothing inside this app but its data folder (.run, where voice typing's
    environment lives on a PC without a media folder), and media folders only strictly inside
    agent_access.allowed_roots."""
    p = Path(path).resolve()
    home = Path.home().resolve()
    data = _data_dir(profile).resolve()
    if len(p.parts) < 3:
        raise PermissionError(f"{p} is too close to the drive root")
    if _within(home, p):
        raise PermissionError(f"{p} holds the home folder")
    if _within(REPO, p):
        raise PermissionError(f"{p} holds this app")
    if _within(p, REPO) and not (_within(p, data) and p != data):
        raise PermissionError(f"{p} is part of this app")
    if media_folder:
        roots = [Path(x).resolve() for x in paths.allowed_roots(profile)]
        if not paths.inside(str(p), [str(x) for x in roots]) or any(p == x for x in roots):
            raise PermissionError(f"{p} is not a folder inside agent_access.allowed_roots")


def _hf_guard(path: Path, profile: dict) -> None:
    """A model folder in the Hugging Face cache: <HF home>/hub/models--<owner>--<name>, nothing else."""
    p = Path(path)
    if p.parent.resolve() != (hf_home(profile) / "hub").resolve() or not p.name.startswith("models--"):
        raise PermissionError(f"{p} is not a model folder in the Hugging Face cache")


def _check(item: Item, profile: dict) -> None:
    """_guard, and that the folder is what it should be."""
    p = Path(item.path)
    _guard(p, profile, item.media)
    if item.kind == "hf":
        _hf_guard(p, profile)
    elif item.kind == "comfyui" and not ((p / "main.py").is_file() or (p / "comfy").is_dir()):
        raise PermissionError(f"{p} does not look like ComfyUI (no main.py)")
    elif item.kind == "whisper" and not ((p / "whisper_mcp.py").is_file() or (p / ".venv" / "pyvenv.cfg").is_file()):
        raise PermissionError(f"{p} does not look like the recordings server (no whisper_mcp.py)")
    elif item.kind == "venv":
        if p.name != ".venv" or not (p / "pyvenv.cfg").is_file():
            raise PermissionError(f"{p} is not a Python environment")
        if not item.media and not _within(p, _data_dir(profile)):
            raise PermissionError(f"{p} is neither inside agent_access.allowed_roots nor in this app's data folder")
    elif item.kind == "file" and not p.is_file():
        raise PermissionError(f"{p} is not a file")


def _on_rm_error(func, path, *_):
    """Windows: read-only files (git objects, some wheels) need their flag cleared, and a file a stopped program
    just let go of can stay locked for a moment."""
    for attempt in range(3):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == 2:
                raise
            time.sleep(0.5)


def delete_tree(path: str | Path, profile: dict, media_folder: bool, report=lambda *a: None,
                hf_model: bool = False) -> int:
    """Delete a folder (or one file) after _guard; returns the bytes it held. One that is not there is fine.
    hf_model: a model folder in the Hugging Face cache, checked by _hf_guard as well."""
    p = Path(path)
    if not p.exists():
        return 0
    _guard(p, profile, media_folder)
    if hf_model:
        _hf_guard(p, profile)
    size = dir_bytes(p)
    report(f"deleting {short_path(p)} ({features_gb(size / 1e9)})")
    if p.is_file():
        p.unlink()
    elif sys.version_info >= (3, 12):
        shutil.rmtree(p, onexc=_on_rm_error)
    else:
        shutil.rmtree(p, onerror=_on_rm_error)
    return size


def _delete_item(item: Item, profile: dict, report) -> int:
    if not item.path or not Path(item.path).exists():
        return 0
    _check(item, profile)
    return delete_tree(item.path, profile, item.media, report, hf_model=item.kind == "hf")


def _run(cmd: list, env: dict | None = None) -> subprocess.CompletedProcess:
    info("  $ " + " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], env=env, capture_output=True, text=True, check=False,
                          creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0)


def _switch_off(profile: dict, fid: str, report) -> dict:
    """Turn the feature off as the Settings tab does, which stops its service and restarts what depends on it.
    Returns the profile after the change."""
    from . import profile as prof
    from . import settings

    sid = SWITCH_SETTING.get(fid)
    if not sid:
        return profile
    if settings.current_values(profile).get(sid) is False:
        return profile
    report(f"turning {features.BY_ID[fid].short} off")
    settings.apply(profile, {sid: False}, log=lambda msg: info(f"      {msg}"))
    return prof.resolve_profile(profile["name"])


def _stop(profile: dict, svcs: list[str]) -> None:
    from . import services

    services.stop(profile, svcs)


def _wait_released(items: list[Item], report) -> None:
    """Wait until no process runs from a program folder about to go; a program started outside the stack is named."""
    folders = [i.path for i in items if i.kind in PROGRAM_KINDS and i.path]
    deadline = time.monotonic() + STOP_WAIT_S
    while True:
        busy = {f: pids for f in folders if (pids := running_from(f))}
        if not busy:
            return
        if time.monotonic() > deadline:
            folder, pids = next(iter(busy.items()))
            raise RuntimeError(f"a program still runs from {short_path(folder)} (pid {', '.join(map(str, pids))}); "
                               "stop it, then remove again. Nothing was deleted")
        report("waiting for the program to stop")
        time.sleep(1)


def _reset_openwebui_stt(profile: dict) -> bool:
    """Open WebUI's microphone back to its own Whisper when it points at voice typing's endpoint (port 8790): without
    voice typing every recording there would fail. Backed up first (media.provision_openwebui)."""
    import json
    import sqlite3

    from . import media

    db = media.openwebui_db(profile)
    if not db.exists():
        return False
    try:
        con = sqlite3.connect(db, timeout=30)
        try:
            rows = dict(con.execute("select key, value from config where key in "
                                    "('audio.stt.engine', 'audio.stt.openai.api_base_url')").fetchall())
        finally:
            con.close()
    except sqlite3.Error:
        return False
    engine = json.loads(rows.get("audio.stt.engine") or '""')
    url = json.loads(rows.get("audio.stt.openai.api_base_url") or '""')
    port = str((profile.get("ports") or {}).get("dictation", 8790))
    if engine != "openai" or f"127.0.0.1:{port}" not in str(url):
        return False
    return bool(media.provision_openwebui(db, {"audio.stt.engine": ""}))


# ---------------------------------------------------------------- remove

def remove(profile: dict, fid: str, report=lambda *a: None) -> str:
    """Remove one feature (see the module docstring). Raises when it cannot; what was done so far stays done, and the
    feature still reads as installed until its program folder goes, so Remove can run again."""
    from . import profile as prof
    from . import settings

    r = plan(profile, fid)
    if r.blocked:
        raise RuntimeError(r.blocked)
    notes: list[str] = []
    freed = 0
    if fid == "voice_typing" and _reset_openwebui_stt(profile):   # before its endpoint goes away
        notes.append("Open WebUI's microphone uses its own Whisper again")
    if "read_aloud" in r.also and settings.current_values(profile).get(SWITCH_SETTING["read_aloud"]):
        # Only written: the voice typing app it runs in stops for good below, so restarting it now would be wasted.
        settings.save(profile, {SWITCH_SETTING["read_aloud"]: False})
        profile = prof.resolve_profile(profile["name"])
    profile = _switch_off(profile, fid, report)
    files = [i for i in r.deletes if i.kind in ("hf", "file") and i.path]
    programs = [i for i in r.deletes if i.kind in PROGRAM_KINDS and i.path]
    if fid in TOOL_ENV:
        from . import services

        _stop(profile, ["open_webui" if fid == "chat" else "phoenix"])
        root = _tool_dir()
        env = root / TOOL_ENV[fid] if root else None
        if env and env.exists():
            size = dir_bytes(env)
            report(f"uninstalling the uv tool {TOOL_ENV[fid]}")
            done = _run([which("uv") or "uv", "tool", "uninstall", TOOL_ENV[fid]])
            if done.returncode and env.exists():
                raise RuntimeError(f"uv could not uninstall {TOOL_ENV[fid]}: {(done.stderr or done.stdout).strip()[-300:]}")
            services._uv_tool_dir_cache.clear()
            freed += size
            notes.append(f"uninstalled {TOOL_ENV[fid]}")
        else:
            notes.append(f"{TOOL_ENV[fid]} was not installed; turned it off")
    elif fid == "images":
        from . import media

        _stop(profile, ["comfyui"])
        _wait_released(programs, report)
        if media.provision_openwebui(media.openwebui_db(profile), {"image_generation.enable": False}):
            notes.append("turned off Open WebUI's image button")
        for item in files + programs:   # model files first, ComfyUI's folder last
            freed += _delete_item(item, profile, report)
        notes.append("removed ComfyUI and its models" if programs else "turned image generation off")
    elif fid == "voice_typing":
        from . import dictation

        _stop(profile, ["dictation"])
        _wait_released(programs, report)
        for item in files + programs:   # Whisper and Kokoro first, the environment last
            freed += _delete_item(item, profile, report)
        env_dir = dictation.env_dir(profile)
        if programs and env_dir.name == "dictation" and env_dir.exists() and not any(env_dir.iterdir()):
            env_dir.rmdir()   # the empty folder the installer made for it
        notes.append("removed voice typing" + (" and read aloud" if r.also else ""))
    elif fid == "read_aloud":
        for item in files:   # Kokoro first, then the packages that make it read as installed
            freed += _delete_item(item, profile, report)
        freed += _remove_read_aloud_packages(profile, report)
        notes.append("removed read aloud")
    elif fid == "recordings":
        from . import whisper

        if features.desktop_entry() is not None:
            report("removing the server from Claude Desktop's config")
            notes.append(whisper.unregister_desktop())
        _wait_released(programs, report)
        for item in files + programs:
            freed += _delete_item(item, profile, report)
        notes.append("removed recordings; restart Claude Desktop to drop the server from its list")
    elif fid == "openclaw":
        npm = which("npm")
        if not npm:
            raise RuntimeError("npm was not found, so OpenClaw cannot be uninstalled from here")
        size = dir_bytes(_openclaw_dir()) if _openclaw_dir() else 0
        report("npm uninstall -g openclaw")
        done = _run([npm, "uninstall", "-g", "openclaw"])
        if done.returncode:
            raise RuntimeError(f"npm uninstall -g openclaw exited with code {done.returncode}: "
                               f"{(done.stderr or done.stdout).strip()[-300:]}")
        freed += size
        notes.append("uninstalled OpenClaw")
    return "; ".join(notes) + (f"; freed {features_gb(freed / 1e9)}" if freed else "")


def _remove_read_aloud_packages(profile: dict, report) -> int:
    """Take read aloud's packages out of voice typing's environment, with the app stopped while files change (Windows
    locks a loaded DLL). With the GPU runtime in, the CPU onnxruntime voice typing needs (Silero VAD) goes back in and
    must import before the app starts again; when it does not, the app stays stopped and the error says how to
    repair it."""
    from . import dictation, services

    if not dictation.installed(profile):
        return 0
    python = dictation.env_python(profile)
    site = dictation._site_packages(profile)
    gpu = dictation.read_aloud_gpu_installed(profile)
    names = [p.split("==")[0] for p in dictation.READ_PACKAGES
             if (site / p.split("==")[0].replace("-", "_")).exists()]
    if gpu:
        names += [p.split("==")[0] for p in reversed(dictation.READ_GPU_PACKAGES)]   # cuDNN, then ONNX Runtime
    if not names:
        return 0
    before = dir_bytes(site)
    was_up = bool(next((r for r in services.status(profile) if r["service"] == "dictation"), {}).get("healthy"))
    if was_up:
        report("stopping voice typing while its packages change")
        services.stop(profile, ["dictation"])
    uv = which("uv") or "uv"
    report(f"uninstalling {', '.join(names)} from voice typing's environment")
    done = _run([uv, "pip", "uninstall", "--python", python, *names])
    if done.returncode:
        if was_up:
            services.start(profile, ["dictation"])
        raise RuntimeError(f"uv could not uninstall {', '.join(names)}: {(done.stderr or done.stdout).strip()[-300:]}")
    if gpu:
        cpu = next((p for p in dictation.PACKAGES if p.startswith("onnxruntime==")), "onnxruntime")
        report(f"installing {cpu} for voice typing")
        done = _run([uv, "pip", "install", "--python", python, "--reinstall", cpu])
        check = _run([python, "-c", "import onnxruntime"]) if not done.returncode else done
        if done.returncode or check.returncode:
            raise RuntimeError(f"voice typing needs {cpu} back, and it did not install or import; voice typing stays "
                               "stopped until `uv run scripts/stack.py dictate install` repairs it")
    if was_up:
        services.start(profile, ["dictation"])
    return max(0, before - dir_bytes(site))


# ---------------------------------------------------------------- Ollama models

@dataclass
class ModelRow:
    name: str
    size_gb: float          # on disk when downloaded, else the catalog's download size
    downloaded: bool
    use: str                # "chat, small tier", "embeddings", ... or "" when the profile does not use it
    in_catalog: bool
    notes: str = ""
    role: str = ""          # the catalog's role: fim, embed, small, primary, reviewer


ROLE_NAMES = {"primary": "chat", "small": "small tier", "embed": "embeddings", "fim": "autocomplete",
              "reviewer": "reviewer"}


def uses(profile: dict, name: str) -> list[str]:
    """What the profile uses an Ollama model for: its roles (primary, small, embed, fim, reviewer)."""
    m = profile.get("models") or {}
    base = name.removesuffix(":latest")
    return [ROLE_NAMES[r] for r in ("primary", "small", "embed", "fim", "reviewer")
            if m.get(r) and str(m.get(r)).removesuffix(":latest") == base]


def model_rows(profile: dict) -> list[ModelRow]:
    """Every Ollama model to show: the catalog's, then any other model Ollama has. Sizes from Ollama when it runs."""
    from . import ollama

    port = (profile.get("ports") or {}).get("ollama", 11434)
    have: dict[str, float] = {}
    try:
        for t in ollama.api(f"http://127.0.0.1:{port}", "/api/tags", timeout=5).get("models", []):
            have[str(t.get("name") or "")] = float(t.get("size") or 0) / 1e9
    except (urllib.error.URLError, OSError, ValueError):
        have = {}
    if not have:   # Ollama is off: look for the manifests where it keeps them
        store = features.effective_model_store(profile)
        for name in profile.get("catalog") or {}:
            if features.manifest_path(store, name).is_file():
                have[name] = float((profile["catalog"].get(name) or {}).get("size_gb") or 0)
    rows = []
    cat = profile.get("catalog") or {}
    for name, c in cat.items():
        latest = have.get(name, have.get(f"{name}:latest"))
        rows.append(ModelRow(name, latest if latest is not None else float((c or {}).get("size_gb") or 0),
                             latest is not None, ", ".join(uses(profile, name)), True, str((c or {}).get("notes") or ""),
                             str((c or {}).get("role") or "")))
    for name, gb in sorted(have.items()):
        base = name.removesuffix(":latest")
        if name not in cat and base not in cat:
            rows.append(ModelRow(base, gb, True, ", ".join(uses(profile, name) or uses(profile, base)), False))
    return rows


def remove_model(profile: dict, name: str) -> str:
    """Delete a downloaded Ollama model (Ollama's DELETE /api/delete). Refused while the profile uses it: the gateway
    would answer with errors until Settings names another model."""
    import json
    import urllib.request

    used = uses(profile, name)
    if used:
        raise RuntimeError(f"{name} is in use ({', '.join(used)}); pick another model in Settings first")
    port = (profile.get("ports") or {}).get("ollama", 11434)
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/delete",
                                 data=json.dumps({"model": name, "name": name}).encode(),
                                 method="DELETE", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60):
            pass
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Ollama could not delete {name}: HTTP {e.code}") from e
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(f"Ollama does not answer, so {name} was not deleted: {e}") from e
    features._tags_cache.clear()
    return f"deleted {name}"


def download_model(profile: dict, name: str, on_progress=None) -> str:
    """Pull an Ollama model (the catalog's or any tag), with progress (fraction, done bytes, total bytes)."""
    from . import ollama

    port = (profile.get("ports") or {}).get("ollama", 11434)
    base = f"http://127.0.0.1:{port}"
    if not ollama.version(base):
        raise RuntimeError("Ollama does not answer; start it first")
    ollama.pull_stream(base, name, on_progress)
    features._tags_cache.clear()
    return f"downloaded {name}"
