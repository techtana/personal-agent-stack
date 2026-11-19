"""Installer back end: which features, where the models and tools go, then the setup steps in a background worker.

The installer window (scripts/installer.py) or `stack.py install --no-gui` asks which optional features to install
or remove (stacklib/features.py: what each costs on this PC, and what is installed already) and for the folders, checks
them, writes the choice into machines/<HOST>.yaml (save_paths, save_features) and starts `stack.py install --worker` as
a detached process. The worker runs plan_steps(plan): one removal step per feature or model to remove
(stacklib/uninstall.py), then STEPS (or the few of them plan.only names), and records its progress in
.run/install/state.json, so the window can be closed and opened again while it works. The tray's Features card starts
the same worker for one feature (start_feature) or a removal (start_removal) and reads the same state.
`stack.py setup` runs STEPS in the foreground with the folders and features already in the profile.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import yaml

from . import ENV_FILE, IS_WINDOWS, REPO, info, load_dotenv, warn, which
from . import agents_build, catalog, claude_access, claude_env, clients, disks, features, litellm_build, media, ollama, procname, services, winget_build
from . import profile as prof

INSTALL_DIR = REPO / ".run" / "install"   # under the repository, not data_dir: it must not move while setup runs
STATE_FILE = INSTALL_DIR / "state.json"
PLAN_FILE = INSTALL_DIR / "plan.json"
LOG_FILE = INSTALL_DIR / "install.log"

# uv tool environments: (tool, environment name, install spec, python), from config/installer.yaml python_tools.
TOOLS = tuple((tid, t["env"], [str(a) for a in t["install"]], str(t["python"]))
              for tid, t in catalog.python_tools().items() if tid in ("litellm", "phoenix", "open-webui"))
TOOL_FEATURES = ("gateway", "chat", "tracing")   # the features whose programs are uv tools (LiteLLM, Open WebUI, Phoenix)
LONG_PATH = 60      # Python packages with deep trees (spaCy, HF cache) break past 260 characters on Windows
HF_TOOL = (catalog.tool("hf")["env"], [str(a) for a in catalog.tool("hf")["install"]],
           str(catalog.tool("hf")["python"]))   # environment name, install spec, python: the `hf` command
HF_CACHE_DIRS = ("hub", "xet", "datasets", "assets")       # what moves from an earlier HF_HOME; the token stays put


@dataclass
class Plan:
    model_store: str                # OLLAMA_MODELS
    tool_dir: str = ""              # UV_TOOL_DIR; "" keeps whatever `uv tool dir` reports
    move_models_from: str = ""      # an earlier model store whose blobs and manifests move into model_store
    install_ollama: bool = False
    pull: bool = True
    restart_ollama: bool = True
    start_stack: bool = False
    check_disks: bool = True
    setup_huggingface: bool = True
    hf_home: str = ""               # HF_HOME; "" puts it next to the models (<models drive>\\huggingface on Windows)
    install_openclaw: bool = False  # may upgrade Node.js machine-wide, so only when chosen in the installer
    setup_openclaw: bool = False    # onboard OpenClaw if needed and make the gateway its only model endpoint
    setup_media: bool = True        # ComfyUI and the image model under media.root, when the profile has one
    media_root: str = ""            # chosen in the installer: written to media.root and agent_access.allowed_roots
    remove: list[str] = field(default_factory=list)          # features to remove first (stacklib/uninstall.py)
    remove_models: list[str] = field(default_factory=list)   # downloaded Ollama models to delete
    pull_models: list[str] = field(default_factory=list)     # more Ollama models to download (the tray's Download)
    only: list[str] | None = None   # the STEPS ids to run after the removals; None runs them all, [] none
    targets: list[str] = field(default_factory=list)   # the features this run is for, so the tray can mark their rows
    voice_packs: list[str] = field(default_factory=list)     # read aloud voices to download (voice_packs keys)
    remove_voices: list[str] = field(default_factory=list)   # read aloud voices to delete


@dataclass
class PathCheck:
    ok: bool
    message: str
    free_gb: float | None = None


# ---------------------------------------------------------------- folder choice

def _nearest_existing(p: Path) -> Path:
    while not p.exists() and p != p.parent:
        p = p.parent
    return p


def drive_present(path: str) -> bool:
    p = Path(path).expanduser()
    return p.is_absolute() and Path(p.anchor).exists()


def check_dir(path: str, need_gb: float, models: bool = False) -> PathCheck:
    """Can `path` be created and hold need_gb more? The message is shown under the folder field as is.
    models: the folder is for Ollama's models, so it must match the Ollama app's own Model location when one is set."""
    if not path.strip():
        return PathCheck(False, "Choose a folder.")
    p = Path(path.strip()).expanduser()
    if not p.is_absolute():
        return PathCheck(False, "Use a full path, for example C:\\ollama\\models.")
    if models:
        note = features.store_override_note({}, str(p))
        if note:
            return PathCheck(False, note)
    if not Path(p.anchor).exists():
        return PathCheck(False, f"Drive {p.drive or p.anchor} is not connected.")
    if p.exists() and not p.is_dir():
        return PathCheck(False, f"{p} is a file, not a folder.")
    base = _nearest_existing(p)
    if not base.is_dir():
        return PathCheck(False, f"{base} is a file, so the folder cannot be created there.")
    free = shutil.disk_usage(base).free / 1e9
    where = p.drive or p.anchor
    if free < need_gb:
        return PathCheck(False, f"Needs about {need_gb:.1f} GB, but {where} has {free:.1f} GB free.", free)
    msg = f"{where} has {free:.0f} GB free; this needs about {need_gb:.1f} GB."
    if IS_WINDOWS and len(str(p)) > LONG_PATH:
        msg += f" Long path ({len(str(p))} characters): a shorter one avoids Windows' 260-character limit."
    return PathCheck(True, msg, free)


def dir_size_gb(path: str | Path) -> float:
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / 1e9


def has_models(path: str | Path) -> bool:
    return bool(path) and (Path(path) / "manifests").is_dir() and (Path(path) / "blobs").is_dir()


def same_drive(a: str, b: str) -> bool:
    return Path(a).anchor.lower() == Path(b).anchor.lower()


models_to_pull = features.models_to_pull


def pull_size_gb(profile: dict, models: list[str]) -> float:
    return sum(float((profile["catalog"].get(x) or {}).get("size_gb", 0)) for x in models)


def current_tool_dir() -> str:
    d = services._uv_tool_dir()
    return str(d) if d else ""


def _git(*args: str, timeout: float = 10) -> str | None:
    """Output of a git command in the repository, or None when git is missing, fails or times out."""
    git = which("git")
    if not git:
        return None
    try:
        r = subprocess.run([git, "-C", str(REPO), *args], capture_output=True, text=True, timeout=timeout,
                           creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def checkout_behind(fetch: bool = True) -> str:
    """A warning when this checkout lacks commits of origin's default branch, else "".

    An old checkout installs an old stack: on 2026-11-07 a reinstall from a checkout 10 commits behind origin/main
    had no voice typing step and no Start menu entry, with nothing to say why."""
    from . import deploy

    if deploy.is_app():   # an installed app is no checkout: the source's state was recorded when it was copied here
        return deploy.read_marker().get("behind") or ""
    if _git("rev-parse", "--is-inside-work-tree") != "true":
        return ""
    ref = (_git("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD") or "origin/main")
    fetched = not fetch or _git("fetch", "--quiet", "origin", ref.split("/", 1)[1], timeout=20) is not None
    count = _git("rev-list", "--count", f"HEAD..{ref}")
    if not count or not count.isdigit() or int(count) == 0:
        return ""
    n = int(count)
    stale = "" if fetched else " (as of the last fetch; GitHub could not be reached)"
    return (f"This folder is {n} commit{'s' if n != 1 else ''} behind {ref}{stale}, so setup would install an older "
            f"stack and miss newer steps. Close the installer, run `git pull` in {REPO}, then start install.cmd again "
            "from there.")


def defaults(profile: dict) -> dict:
    """What the installer offers first, and why."""
    configured = profile["ollama_env"].get("OLLAMA_MODELS") or profile["model_store"] or ""
    fallback = str(Path.home() / ".ollama" / "models")   # Ollama's own default
    note = ""
    app = features.app_model_store()   # the Ollama app's Model location overrides OLLAMA_MODELS, so offer it
    if app and drive_present(app):
        if configured and Path(configured) != Path(app):
            note = (f"machines/{profile['name']}.yaml had {configured}, but the Ollama app's own Settings > Model "
                    f"location is {app}, and Ollama uses that one.")
        configured = app
    if configured and drive_present(configured):
        store = configured
    else:
        store = fallback
        if configured:
            note = f"machines/{profile['name']}.yaml had {configured}, but drive {Path(configured).drive or Path(configured).anchor} is not connected."
    move_from = ""
    for cand in dict.fromkeys(x for x in (configured, fallback) if x):
        if drive_present(cand) and has_models(cand):
            move_from = cand
            break
    models = models_to_pull(profile)
    hw = features.hardware(profile)
    status = features.statuses(profile)
    return {
        "model_store": store,
        "model_note": note,
        "move_from": move_from,
        "move_gb": dir_size_gb(move_from) if move_from else 0.0,
        "tool_dir": current_tool_dir(),
        "ollama_missing": not which("ollama"),
        "models": models,
        "models_gb": pull_size_gb(profile, models),
        "media_root": default_media_root(profile, store),
        "media_installed": media.comfyui_installed(profile),
        # The features page: this PC, what each feature costs on it, what is installed, and what to tick first.
        "hardware": hw,
        "features": status,
        "estimates": features.estimates(profile, hw),
        "choice": features.initial_choice(status, hw),
        "options": features.current_options(profile),
    }


def chosen_with_required(chosen) -> set[str]:
    """The choice plus the required features and the ones a chosen feature runs inside (read aloud: voice typing)."""
    return features.with_requirements(set(chosen) | {f.id for f in features.FEATURES if f.required})


def tools_need_gb(chosen, est: dict, status: dict, moving: bool = False) -> float:
    """Space the Python tools folder needs for the chosen features: the tools not installed yet, or all of them when
    the folder moves (uv installs them again there). 0.1 GB when nothing is new, so a full drive still shows."""
    chosen = chosen_with_required(chosen)
    need = sum(est[f].disk_gb for f in TOOL_FEATURES if f in chosen and (moving or not status[f].installed))
    return need or 0.1


def media_need_gb(chosen, est: dict, status: dict, moved: bool = False) -> float:
    """Space the media folder needs: ComfyUI and Whisper for recordings, plus voice typing's environment, which goes
    there when the profile has a media folder. Shared downloads (the Whisper model) count once. `moved`: the folder
    differs from the profile's media.root, so what is installed in the old one is installed again."""
    ids = [f for f in ("images", "voice_typing", "read_aloud") if f in set(chosen)]
    installed = set() if moved else {f for f in ids if status[f].installed}
    return features.download_gb(ids, est, installed, full=moved) or 0.1


def media_moved(profile: dict, root: str) -> bool:
    current = (profile.get("media") or {}).get("root") or ""
    return bool(current and root) and Path(root) != Path(current)


def store_need_gb(d: dict, profile: dict, store: str, pull: bool, move_from: str = "") -> float:
    """Space the models folder needs: the models not pulled yet when it is the profile's folder, all of them in another
    one, plus the models that move there from another drive."""
    models = d["estimates"]["models"]
    same = bool(store) and Path(store) == Path(features.model_store(profile))
    if not pull:
        need = 0.1
    elif same and models.todo_gb is not None:
        need = max(models.todo_gb, 0.1)
    else:
        need = d["models_gb"]
    if move_from and store and Path(store) != Path(move_from) and not same_drive(move_from, store):
        need += d["move_gb"]
    return need


def needs_media(chosen) -> bool:
    return any(features.BY_ID[f].needs_media for f in chosen if f in features.BY_ID)


# The setup steps that install (or repair) one feature, for the tray's Install button: the rest of STEPS do not touch it.
FEATURE_STEPS = {
    "models": ["pull"],
    "gateway": ["secrets", "tools", "build"],
    "chat": ["secrets", "tools", "build"],
    "tracing": ["tools", "build"],
    "images": ["media"],
    "voice_typing": ["secrets", "dictation"],
    "read_aloud": ["dictation", "read_aloud"],
    "openclaw": ["openclaw"],
}


def feature_plan(chosen, status: dict) -> dict:
    """Plan fields for the features chosen on the installer's first page. The switches that the machine profile holds
    (Open WebUI, Phoenix, ComfyUI, voice typing) are written by save_features before the worker starts."""
    chosen = set(chosen)
    openclaw = status.get("openclaw")
    return {
        "setup_media": "images" in chosen,
        "install_openclaw": "openclaw" in chosen and not (openclaw and openclaw.installed),
        "setup_openclaw": "openclaw" in chosen,
    }


def wanted_tools(profile: dict) -> list[tuple]:
    out = []
    for tool, env_name, spec, py in TOOLS:
        if tool == "open-webui" and profile["services"].get("open_webui") != "native":
            continue
        if tool == "phoenix" and not profile["observability"].get("phoenix"):
            continue
        out.append((tool, env_name, spec, py))
    return out


def tools_missing(profile: dict, tool_dir: str) -> list[str]:
    root = Path(tool_dir) if tool_dir else None
    return [t for t, env_name, _, _ in wanted_tools(profile) if not (root and (root / env_name / "pyvenv.cfg").exists())]


def _set_top_key(text: str, key: str, value: str) -> str:
    rendered = yaml.safe_dump(value, default_style="'").strip().removesuffix("...").strip()
    pat = re.compile(rf"^{re.escape(key)}:(?P<val>[^#\n]*?)(?P<comment>\s+#.*)?$", re.M)
    if pat.search(text):
        return pat.sub(lambda mt: f"{key}: {rendered}{mt['comment'] or ''}", text, count=1)
    return text.rstrip("\n") + f"\n{key}: {rendered}\n"


def save_paths(profile: dict, model_store: str) -> Path:
    """Write the models folder into machines/<HOST>.yaml (model_store and ollama_env.OLLAMA_MODELS), keeping comments."""
    from .settings import set_key

    path = prof.machine_file(profile["name"])
    text = path.read_text(encoding="utf-8")
    text = _set_top_key(text, "model_store", model_store)
    text = set_key(text, "ollama_env", "OLLAMA_MODELS", model_store)
    parsed = yaml.safe_load(text)
    if parsed.get("model_store") != model_store or (parsed.get("ollama_env") or {}).get("OLLAMA_MODELS") != model_store:
        raise ValueError(f"could not write the models folder into {path.name} safely; edit it by hand")
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def default_media_root(profile: dict, model_store: str) -> str:
    """The profile's media.root, else <models drive>\\media on Windows (next to the other large model files)."""
    if (profile.get("media") or {}).get("root"):
        return profile["media"]["root"]
    if IS_WINDOWS and model_store:
        return str(Path(Path(model_store).anchor) / "media")
    return str(Path.home() / "media")


def _with_media_root(text: str, profile: dict, root: str) -> tuple[str, list[str]]:
    """media.root, and the folder (plus HF_HOME's, when set) added to agent_access.allowed_roots, the path guard's list."""
    from .yamledit import set_key

    roots = list((((yaml.safe_load(text) or {}).get("agent_access") or {}).get("allowed_roots")) or [])
    for want in (root, (profile.get("media") or {}).get("hf_home") or ""):
        if want and not any(Path(want) == Path(r) for r in roots):
            roots.append(want)
    text = set_key(text, "media", "root", root)
    return set_key(text, "agent_access", "allowed_roots", roots), roots


def _write_checked(path: Path, text: str, want: dict[tuple[str, str], object], what: str) -> None:
    """Write the machine file only when every (section, key) reads back as wanted: a layout the line editor cannot
    handle must not leave a half-changed profile."""
    parsed = yaml.safe_load(text) or {}
    for (section, key), value in want.items():
        if (parsed.get(section) or {}).get(key) != value:
            raise ValueError(f"could not write {what} into {path.name} safely ({section}.{key}); edit it by hand")
    path.write_text(text, encoding="utf-8", newline="\n")


def save_media(profile: dict, root: str) -> Path:
    """Write the owner's media folder into machines/<HOST>.yaml: media.root, services.comfyui native, and the folder
    (plus HF_HOME's, when set) added to agent_access.allowed_roots, the path guard's list."""
    from .yamledit import set_key

    path = prof.machine_file(profile["name"])
    text, roots = _with_media_root(path.read_text(encoding="utf-8"), profile, root)
    text = set_key(text, "services", "comfyui", "native")
    _write_checked(path, text, {("media", "root"): root, ("agent_access", "allowed_roots"): roots}, "the media folder")
    return path


FEATURE_SWITCHES = features.SWITCHES   # (section, key, on, off) per optional feature the profile switches


def explicit_options(profile: dict) -> set[tuple[str, str]]:
    """The installer's options that machines/<HOST>.yaml sets itself (the owner's or an earlier install's choice), as
    opposed to defaults from the hardware class or machines/_defaults.yaml: the system check's recommendations replace
    only the defaults."""
    try:
        machine = prof.load_machine(profile.get("name"))
    except Exception:  # noqa: BLE001 - an unreadable file sets nothing; setup reports it elsewhere
        return set()
    out = set()
    for opts in features.OPTIONS.values():
        for opt, _fn in opts:
            if ((machine.get(opt.section) or {}) if isinstance(machine, dict) else {}).get(opt.key) is not None:
                out.add((opt.section, opt.key))
    return out


def option_edits(profile: dict, chosen, options: dict[tuple[str, str], str]) -> dict[tuple[str, str], object]:
    """The (section, key) values that the chosen features' options change. A new chat model also sets
    models.primary_options (memory-mapped experts for an MoE model, as Settings' "Memory-map primary weights"), and the
    small model's context follows the primary's when both are one model, or Ollama reloads it between tiers."""
    out: dict[tuple[str, str], object] = {}
    now = features.current_options(profile)   # the profile's values, defaults filled in
    for fid in chosen:
        for opt, _fn in features.OPTIONS.get(fid, []):
            k = (opt.section, opt.key)
            if k in options and str(options[k]) != now[k]:
                out[k] = features.option_value(opt.section, opt.key, options[k])
    m = profile.get("models") or {}
    primary = out.get(("models", "primary"), m.get("primary"))
    ctx = out.get(("models", "primary_num_ctx"), m.get("primary_num_ctx"))
    if ("models", "primary") in out:
        mmap = {"use_mmap": True} if features.is_moe(profile, primary) else {}
        if (m.get("primary_options") or {}) != mmap:
            out[("models", "primary_options")] = mmap
    if out.keys() & {("models", "primary"), ("models", "primary_num_ctx")} and m.get("small") == primary \
            and m.get("small_num_ctx") != ctx:
        out[("models", "small_num_ctx")] = ctx
    return out


def save_features(profile: dict, chosen, media_root: str = "", status: dict | None = None,
                  options: dict[tuple[str, str], str] | None = None, remove=(), packs=None) -> Path | None:
    """Write what the installer's features page chose into machines/<HOST>.yaml, keeping comments: the switches in
    FEATURE_SWITCHES, the options chosen next to the features (option_edits), and the media folder when a chosen
    feature installs there. Only values that change are written.

    A feature that is installed and on stays on, whatever `chosen` says: the installer adds features and turns one off
    only to remove it, and that switch is left to the removal step (`remove`), which turns it off the way Settings does
    and stops what runs. A feature whose check failed keeps its switch as it is. Returns the file, or None when nothing
    changed."""
    from .yamledit import set_key

    status = features.statuses(profile) if status is None else status
    remove = set(remove)
    chosen = (chosen_with_required(chosen) | {fid for fid in status if features.locked(fid, status)}) - remove
    path = prof.machine_file(profile["name"])
    text = original = path.read_text(encoding="utf-8")
    want: dict[tuple[str, str], object] = {}
    for fid, (section, key, on, off) in FEATURE_SWITCHES.items():
        if (fid in status and status[fid].unknown) or fid in remove:
            continue
        value = on if fid in chosen else off
        have = profile.get(section)   # a profile without the section at all (read_aloud before it existed): off
        if (have or {}).get(key, off if have is None else None) != value:
            text = set_key(text, section, key, value)
            want[(section, key)] = value
    if media_root and needs_media(chosen) and (profile.get("media") or {}).get("root") != media_root:
        text, roots = _with_media_root(text, profile, media_root)
        want.update({("media", "root"): media_root, ("agent_access", "allowed_roots"): roots})
    have_packs = list((profile.get("read_aloud") or {}).get("packs") or [])
    if packs is not None and "read_aloud" in chosen and sorted(packs) != sorted(have_packs):
        text = set_key(text, "read_aloud", "packs", list(packs))   # the read aloud step downloads them
        want[("read_aloud", "packs")] = list(packs)
    for (section, key), value in option_edits(profile, chosen, options or {}).items():
        text = set_key(text, section, key, value)
        want[(section, key)] = value
    if text == original:
        return None
    _write_checked(path, text, want, "the chosen features")
    return path


# ---------------------------------------------------------------- progress

class Skip(Exception):
    """The step does not apply; its message says why."""


class Warn(Exception):
    """The step finished, but something needs the owner's attention; its message says what."""


class Progress:
    """Step states for the window (state_file) or the console (state_file None)."""

    def __init__(self, steps: list[tuple[str, str]], state_file: Path | None = None):
        self.state_file = state_file
        self.state = {
            "status": "running", "pid": os.getpid(), "started": services._proc_info(os.getpid())[1],
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "finished_at": None, "log": str(LOG_FILE),
            "steps": [{"id": i, "title": t, "status": "pending", "detail": "", "fraction": None} for i, t in steps],
        }
        self._last_write = 0.0
        self._write(force=True)

    def _step(self, sid: str) -> dict:
        return next(s for s in self.state["steps"] if s["id"] == sid)

    def _write(self, force: bool = False) -> None:
        if not self.state_file or (not force and time.monotonic() - self._last_write < 0.5):
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1), encoding="utf-8")
        os.replace(tmp, self.state_file)
        self._last_write = time.monotonic()

    def begin(self, sid: str) -> None:
        s = self._step(sid)
        s["status"] = "running"
        n = [x["id"] for x in self.state["steps"]].index(sid) + 1
        info(f"[{n}/{len(self.state['steps'])}] {s['title']}")
        self._write(force=True)

    def update(self, sid: str, detail: str | None = None, fraction: float | None = None) -> None:
        s = self._step(sid)
        if detail is not None:
            s["detail"] = detail
        s["fraction"] = fraction
        self._write()

    def end(self, sid: str, status: str, detail: str = "") -> None:
        s = self._step(sid)
        s.update(status=status, detail=detail or s["detail"], fraction=None)
        (warn if status in ("failed", "warning") else info)(f"      {status}{': ' + s['detail'] if s['detail'] else ''}")
        self._write(force=True)

    def finish(self) -> bool:
        failed = [s for s in self.state["steps"] if s["status"] == "failed"]
        warned = any(s["status"] == "warning" for s in self.state["steps"])
        self.state["status"] = "failed" if failed else "warnings" if warned else "done"
        self.state["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._write(force=True)
        return not failed


# ---------------------------------------------------------------- steps

def ensure_env_file() -> dict[str, str]:
    env = load_dotenv()
    changed = False
    generators = (
        ("LITELLM_MASTER_KEY", lambda: "sk-" + secrets.token_hex(24)),
        ("ORCHESTRATOR_BEARER", lambda: secrets.token_urlsafe(32)),
        ("WEBUI_SECRET_KEY", lambda: secrets.token_hex(32)),
        ("DICTATION_BEARER", lambda: secrets.token_urlsafe(32)),  # Open WebUI's microphone -> voice typing
        # Claude Code's own keys for the gateway and the agent tools (claude_access.py), never the stack's
        *((k, lambda k=k: claude_access.new_key(k)) for k in claude_access.CLAUDE_KEYS),
    )
    for k, gen in generators:
        if not env.get(k):
            env[k] = gen()
            changed = True
    env.setdefault("ANTHROPIC_API_KEY", "")
    if changed or not ENV_FILE.exists():
        lines = ["# Generated by `uv run scripts/stack.py setup`; gitignored. Add ANTHROPIC_API_KEY to enable cloud tiers, then rebuild."]
        lines += [f"{k}={v}" for k, v in env.items()]
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        info(f".env: wrote {ENV_FILE.name} ({'new secrets generated' if changed else 'unchanged'})")
    return env


def _base(profile: dict) -> str:
    return f"http://127.0.0.1:{profile['ports']['ollama']}"


def step_secrets(plan: Plan, profile: dict, report) -> str:
    before = ENV_FILE.exists()
    ensure_env_file()
    return "kept the existing .env" if before else "wrote .env with new secrets"


def step_ollama_install(plan: Plan, profile: dict, report) -> str:
    if which("ollama"):
        raise Skip("already installed")
    o = catalog.ollama()
    if not plan.install_ollama:
        raise Skip(f"not installed; install it later from {o['download_page']}, then run setup again")
    if not IS_WINDOWS:
        raise RuntimeError(f"install Ollama with: {o['linux_install']} (needs sudo), then run setup again")
    report(f"winget install {o['winget_id']} (a few minutes)")
    r = subprocess.run(["winget", "install", "--id", o["winget_id"], "--exact", "--silent",
                        "--accept-package-agreements", "--accept-source-agreements"], check=False)
    if not which("ollama"):
        raise RuntimeError(f"winget exited with code {r.returncode} and ollama.exe is still missing")
    return "installed"


def _move_tree(src: Path, dst: Path, report) -> int:
    """Move every file under src into dst, keeping files dst already has. Returns the number moved."""
    files = [p for p in src.rglob("*") if p.is_file()]
    moved = 0
    for i, f in enumerate(files):
        target = dst / f.relative_to(src)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(target))
            moved += 1
        report(f"{i + 1} of {len(files)} files", (i + 1) / len(files))
    return moved


def step_models_move(plan: Plan, profile: dict, report) -> str:
    src, dst = plan.move_models_from, plan.model_store
    if not src:
        raise Skip("nothing to move")
    if Path(src).resolve() == Path(dst).resolve():
        raise Skip("the models are already in that folder")
    if not has_models(src):
        raise Skip(f"no models found in {src}")
    override = features.store_override_note(profile, dst)
    if override:   # moved files would sit where Ollama never looks
        raise Warn(f"not moved. {override}")
    report("stopping Ollama so its files can move")
    ollama.stop()
    moved = 0
    for sub in ("manifests", "blobs"):   # manifests first: a manifest without its blob re-downloads, not breaks
        moved += _move_tree(Path(src) / sub, Path(dst) / sub, report)
    return f"moved {moved} files from {src}; anything left there was already present in the new folder"


def step_ollama_env(plan: Plan, profile: dict, report) -> str:
    if not which("ollama"):
        raise Skip("Ollama is not installed")
    Path(plan.model_store).mkdir(parents=True, exist_ok=True)
    env = {**profile["ollama_env"], "OLLAMA_MODELS": plan.model_store}
    changed = ollama.set_user_env(env)
    base = _base(profile)
    must_restart = bool(changed) or bool(plan.move_models_from) or not ollama.version(base)
    if must_restart and plan.restart_ollama:
        report("restarting Ollama so it reads the new environment")
        ollama.restart(base)
    if not ollama.version(base):
        raise RuntimeError(f"Ollama does not answer at {base}; start it from the Start menu and run setup again")
    override = features.store_override_note(profile, plan.model_store)
    if override:   # the app starts its server with its own folder, whatever OLLAMA_MODELS says
        raise Warn(f"OLLAMA_MODELS is {plan.model_store}, but Ollama will not use it. {override}")
    if changed and not plan.restart_ollama:
        return f"changed {', '.join(changed)}; restart Ollama for them to apply"
    return f"models folder {plan.model_store}" + (f"; changed {', '.join(changed)}" if changed else "")


def _set_persistent_env(name: str, value: str) -> None:
    os.environ[name] = value
    if IS_WINDOWS:
        ollama.set_user_env({name: value})   # writes any variable to HKCU\Environment and broadcasts the change
    else:
        warn(f"add `export {name}={value}` to your shell profile so later shells see it")


def step_tools(plan: Plan, profile: dict, report) -> str:
    uv = which("uv") or "uv"
    moved = bool(plan.tool_dir) and Path(plan.tool_dir) != Path(current_tool_dir() or ".")
    if plan.tool_dir:
        Path(plan.tool_dir).mkdir(parents=True, exist_ok=True)
        if moved or os.environ.get("UV_TOOL_DIR") != plan.tool_dir:
            _set_persistent_env("UV_TOOL_DIR", plan.tool_dir)
            services._uv_tool_dir_cache.clear()
    tool_dir = current_tool_dir()
    todo = tools_missing(profile, tool_dir)
    if not todo:
        return f"already installed in {tool_dir}"
    failed = []
    for i, (tool, env_name, spec, py) in enumerate(t for t in wanted_tools(profile) if t[0] in todo):
        report(f"installing {tool} ({i + 1} of {len(todo)})", i / len(todo))
        # --force: launchers from an earlier tool folder already sit in ~/.local/bin and would make uv refuse.
        r = subprocess.run([uv, "tool", "install", "--force", "--python", py, *spec], check=False)
        if r.returncode:
            failed.append(tool)
    services._uv_tool_dir_cache.clear()
    if failed:
        raise RuntimeError(f"uv could not install {', '.join(failed)}; the log has uv's message")
    return f"installed {', '.join(todo)} in {tool_dir}" + ("; the old tool folder was left as it was" if moved else "")


def default_hf_home(model_store: str) -> str:
    """Next to the models on Windows (<drive>:\\huggingface): both are large files read once into GPU memory."""
    if IS_WINDOWS and model_store:
        return str(Path(Path(model_store).anchor) / "huggingface")
    return str(Path.home() / ".cache" / "huggingface")


def step_disks(plan: Plan, profile: dict, report) -> str:
    """Check this PC (stacklib/syscheck.py): drive speeds, as before, and the GPU, processor, memory and Windows, with
    which of the chosen models and features are not recommended here. Reuses the report the installer's first page
    made when it is young enough, so the drives are not tested twice."""
    if not plan.check_disks:
        raise Skip("not chosen")
    from . import syscheck

    r = syscheck.load(max_age_s=syscheck.REUSE_S)
    reused = r is not None and bool(r.drives)
    if reused:
        r = syscheck.recommend(r, profile)   # the facts stay; the verdicts follow the profile as setup now has it
        try:
            syscheck.save(r)
        except OSError:
            pass
    else:
        r = syscheck.run(profile, report)
    for line in syscheck.lines(r, profile):
        info(f"      {line}")
    speeds = r.speeds()
    need = pull_size_gb(profile, models_to_pull(profile))
    warnings, suggestion = disks.advise(speeds, plan.model_store, plan.tool_dir or current_tool_dir(), need)
    notes = warnings + ([suggestion] if suggestion else [])
    notes += chosen_against_check(r, profile)
    for w in notes:
        warn(w)
    store = next((s for s in speeds if s.root.lower() == disks.drive_of(plan.model_store).lower()), None)
    head = f"models drive {store.summary()}." if store else "; ".join(s.summary() for s in speeds) + "."
    head = (f"{r.describe()}. " + head) if r.gpu.name or r.cpu.name else head
    if reused:
        head += f" (Checked {time.strftime('%H:%M', time.localtime(r.checked_at))} in the installer.)"
    howto = disks.winsat_howto(speeds)
    for line in howto:
        info(f"      {line}")
    if notes:
        raise Warn(" ".join([head, *notes, *howto]))
    return " ".join([head, *howto])


def chosen_against_check(r, profile: dict) -> list[str]:
    """A sentence for each chosen model, setting or feature the system check does not recommend on this PC."""
    from .dictation.models import label as speech_label

    out = []
    m, d = profile.get("models") or {}, profile.get("dictation") or {}
    for key, value, what in (("models.primary", m.get("primary"), "The chat model {}"),
                             ("models.primary_num_ctx", m.get("primary_num_ctx"), "A {}-token context"),
                             ("dictation.model", d.get("model") if profile["services"].get("dictation") == "native"
                              else None, "The speech model {}")):
        v = r.verdict(key, str(value)) if value else None
        if v and v.level in ("not_recommended", "unavailable"):
            name = speech_label(str(value)) if key == "dictation.model" else value
            out.append(f"{what.format(name)} is not recommended on this PC: {v.text}")
    for fid, (section, key, on, _off) in features.SWITCHES.items():
        v = r.verdict(fid)
        if v and v.level in ("not_recommended", "unavailable") and (profile.get(section) or {}).get(key) == on:
            out.append(f"{features.BY_ID[fid].title} is not recommended on this PC: {v.text}")
    return out


def step_huggingface(plan: Plan, profile: dict, report) -> str:
    if not plan.setup_huggingface:
        raise Skip("not chosen")
    old = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface")
    new = Path(plan.hf_home or default_hf_home(plan.model_store))
    if not drive_present(str(new)):
        raise RuntimeError(f"drive {new.drive or new.anchor} is not connected")
    new.mkdir(parents=True, exist_ok=True)
    notes = [f"HF_HOME {new}"]
    if old.resolve() != new.resolve():
        for sub in HF_CACHE_DIRS:
            if (old / sub).is_dir():
                report(f"moving {old / sub} to {new / sub}")
                notes.append(f"moved {_move_tree(old / sub, new / sub, report)} files from {old / sub}")
    _set_persistent_env("HF_HOME", str(new))
    if not same_drive(str(new), str(Path.home())):
        # The token is a credential: keep it on the internal drive, not on one that can be unplugged and carried off.
        token = Path.home() / ".cache" / "huggingface" / "token"
        _set_persistent_env("HF_TOKEN_PATH", str(token))
        notes.append(f"token file stays at {token}")
    env_name, spec, py = HF_TOOL
    if (Path(current_tool_dir() or ".") / env_name / "pyvenv.cfg").exists():
        return "; ".join(notes + ["hf command already installed"])
    report("installing the hf command (huggingface_hub)")
    r = subprocess.run([which("uv") or "uv", "tool", "install", "--force", "--python", py, *spec], check=False)
    if r.returncode:
        raise RuntimeError("; ".join(notes + [f"uv could not install huggingface_hub (exit code {r.returncode})"]))
    return "; ".join(notes + ["installed the hf command"])


def step_media(plan: Plan, profile: dict, report) -> str:
    if not plan.setup_media:
        raise Skip("not chosen")
    if plan.media_root and (profile.get("media") or {}).get("root") != plan.media_root:
        save_media(profile, plan.media_root)
        profile = prof.resolve_profile(profile["name"])
    if profile["services"].get("comfyui") != "native" or not (profile.get("media") or {}).get("root"):
        raise Skip("no media folder in the machine profile (media.root); choose one in the installer to add images")
    if not which("git"):
        raise RuntimeError(f"git is not installed; install it (winget install {winget_build.package_id('git')}) and run "
                           "setup again")
    notes = [media.install_comfyui(profile, report)]
    notes.append(media.install_models(profile, profile["media"].get("image_workflow") or "z_image_turbo", report))
    changed = media.provision_openwebui(media.openwebui_db(profile), media.image_settings(profile))
    if changed:
        notes.append("turned on image generation in Open WebUI (restart it to apply)")
    return "; ".join(notes)


def step_dictation(plan: Plan, profile: dict, report) -> str:
    """Voice typing's environment, only where it is turned on (services.dictation: native); it is opt-in because it
    holds a microphone hotkey and about 1.2 GB of VRAM while loaded."""
    if profile["services"].get("dictation") != "native":
        raise Skip("not chosen; tick Voice typing in the installer, or run `uv run scripts/stack.py dictate install`")
    from . import dictation

    return dictation.install(profile, report)


def step_read_aloud(plan: Plan, profile: dict, report) -> str:
    """Read aloud in voice typing's environment, only where it is turned on (read_aloud.enabled): espeak-ng, comtypes
    and Kokoro's voices. Without it voice typing runs as before, with no speaker button."""
    if not (profile.get("read_aloud") or {}).get("enabled"):
        raise Skip("not chosen; tick Read aloud in the installer, or run `uv run scripts/stack.py read-aloud install`")
    if profile["services"].get("dictation") != "native":
        raise Skip("read aloud runs in the voice typing app, which is off; tick Voice typing too")
    from . import dictation

    return dictation.install_read_aloud(profile, report)


def _version(text: str) -> tuple[int, int, int] | None:
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(x) for x in m.groups()) if m else None


def node_ok_for_openclaw(v: tuple[int, int, int] | None) -> bool:
    """A Node.js version OpenClaw accepts (config/installer.yaml openclaw.node_versions)."""
    return v is not None and any(lo <= v and (hi is None or v < hi) for lo, hi in catalog.node_ranges())


def node_requirement() -> str:
    """"24.22.1+ (below 25.0.0) or 26.12.1+", for messages."""
    return " or ".join(f"{'.'.join(map(str, lo))}+" + (f" (below {'.'.join(map(str, hi))})" if hi else "")
                       for lo, hi in catalog.node_ranges())


def _node_version() -> tuple[int, int, int] | None:
    node = which("node")
    if not node:
        return None
    return _version(subprocess.run([node, "--version"], capture_output=True, text=True, check=False).stdout)


def _dotted(v: tuple | None) -> str:
    return ".".join(map(str, v)) if v else "not installed"


def openclaw_state(profile: dict) -> str:
    """"" when OpenClaw is missing or already uses only the gateway; otherwise its status, for the installer's offer."""
    if not which("openclaw"):
        return ""
    try:
        s = clients.openclaw(profile["ports"]["litellm"])
    except Exception as e:  # noqa: BLE001 - the offer is optional; never block the installer on it
        return f"not checked ({e})"
    return "" if s.level == "ok" else s.state


def _point_openclaw_at_gateway(profile: dict, report, done: str) -> str:
    try:
        return f"{done}{clients.setup_openclaw(profile, report)}"
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as e:
        raise Warn(f"{done}pointing it at the gateway failed: {e}. Fix it with `uv run scripts/stack.py openclaw` "
                   "or Use gateway in the tray") from e


def step_openclaw(plan: Plan, profile: dict, report) -> str:
    if which("openclaw"):
        if not plan.setup_openclaw:
            raise Skip("already installed")
        if not openclaw_state(profile):
            raise Skip("already installed and uses only the gateway")
        return _point_openclaw_at_gateway(profile, report, "")
    if not plan.install_openclaw:
        raise Skip("not chosen")
    oc = catalog.openclaw()
    node = _node_version()
    if not node_ok_for_openclaw(node):
        if not IS_WINDOWS:
            raise RuntimeError(f"OpenClaw needs Node.js {node_requirement()} (found {_dotted(node)}); install it, then run "
                               "setup again")
        report(f"Node.js {_dotted(node)} is too old for OpenClaw; installing the current LTS with winget (Windows asks for admin)")
        # On an existing Node.js LTS install, `winget install` upgrades it in place.
        subprocess.run(["winget", "install", "--id", oc["node_winget_id"], "--exact", "--silent",
                        "--accept-package-agreements", "--accept-source-agreements"], check=False)
        nodejs = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs"
        if nodejs.is_dir() and str(nodejs).lower() not in os.environ.get("PATH", "").lower():
            os.environ["PATH"] = f"{nodejs}{os.pathsep}{os.environ.get('PATH', '')}"   # a fresh install is not on our PATH yet
        node = _node_version()
        if not node_ok_for_openclaw(node):
            raise RuntimeError(f"Node.js is {_dotted(node)} after winget; upgrade it from {oc['node_download_page']}, then "
                               "run setup again")
    npm = which("npm")
    if not npm:
        raise RuntimeError("npm was not found next to Node.js")
    report(f"npm install -g {oc['npm']} (into your user profile on the system drive)")
    r = subprocess.run([npm, "install", "-g", oc["npm"]], check=False)
    if r.returncode:
        raise RuntimeError(f"npm install -g openclaw exited with code {r.returncode}; the log has npm's message")
    if plan.setup_openclaw:
        return _point_openclaw_at_gateway(profile, report, f"installed (Node.js {_dotted(node)}). ")
    return (f"installed (Node.js {_dotted(node)}). Next: `uv run scripts/stack.py openclaw` makes the gateway its only "
            "model provider, so chats stay on this machine")


def _set_packs(profile: dict, packs: list[str]) -> None:
    """Write read_aloud.packs (the Piper voices to keep) into machines/<HOST>.yaml."""
    from .yamledit import set_key

    path = prof.machine_file(profile["name"])
    text = set_key(path.read_text(encoding="utf-8"), "read_aloud", "packs", list(packs))
    _write_checked(path, text, {("read_aloud", "packs"): list(packs)}, "the read aloud voices")


def step_voice_packs(plan: Plan, profile: dict, report) -> str:
    """Read aloud voices chosen one by one (the tray's Download): kept in read_aloud.packs, then downloaded."""
    from . import dictation

    have = list((profile.get("read_aloud") or {}).get("packs") or [])
    want = have + [k for k in plan.voice_packs if k not in have]
    if want != have:
        _set_packs(profile, want)
    return dictation.download_packs(profile, plan.voice_packs, report)


def step_remove_voices(plan: Plan, profile: dict, report) -> str:
    from . import uninstall

    return "; ".join(uninstall.remove_voice_pack(profile, key, report) for key in plan.remove_voices)


def step_pull_more(plan: Plan, profile: dict, report) -> str:
    """Models chosen one by one (the tray's Download), on top of the ones the profile names."""
    from . import uninstall

    done = []
    for i, name in enumerate(plan.pull_models):
        def progress(frac, got, total, i=i, name=name):
            text = f"{name}: {got / 1e9:.1f} of {total / 1e9:.1f} GB" if total else f"{name}: starting"
            report(f"{text} (model {i + 1} of {len(plan.pull_models)})", (i + (frac or 0)) / len(plan.pull_models))
        done.append(uninstall.download_model(profile, name, progress))
    return "; ".join(done)


def step_remove_feature(fid: str):
    """A worker step that removes one feature (stacklib/uninstall.py)."""
    def run(plan: Plan, profile: dict, report) -> str:
        from . import uninstall

        return uninstall.remove(profile, fid, report)
    return run


def step_remove_models(plan: Plan, profile: dict, report) -> str:
    from . import uninstall

    done = []
    for i, name in enumerate(plan.remove_models):
        report(f"deleting {name}", i / len(plan.remove_models))
        done.append(uninstall.remove_model(profile, name))
    return "; ".join(done)


def removal_order(fids) -> list[str]:
    """Features in the order they come off: one that runs inside another first (read aloud before voice typing)."""
    fids = [f.id for f in features.FEATURES if f.id in set(fids)]
    return sorted(fids, key=lambda fid: 0 if features.BY_ID[fid].requires else 1)


def plan_steps(plan: Plan) -> list[tuple]:
    """(id, title, function) of every step this plan runs, in order: removals, then STEPS (all, or plan.only)."""
    out: list[tuple] = []
    for fid in removal_order(plan.remove):
        if fid == "read_aloud" and "voice_typing" in plan.remove:
            continue   # it goes with voice typing's environment
        out.append((f"remove_{fid}", f"Remove {features.BY_ID[fid].short}", step_remove_feature(fid)))
    if plan.remove_models:
        names = ", ".join(plan.remove_models)
        out.append(("remove_models", f"Delete {names}" if len(plan.remove_models) < 3 else "Delete models",
                    step_remove_models))
    only = None if plan.only is None else set(plan.only)
    out += [s for s in STEPS if only is None or s[0] in only]
    if plan.remove_voices:
        out.insert(len([s for s in out if s[0].startswith("remove")]),
                   ("remove_voices", "Delete read aloud voices", step_remove_voices))
    if plan.voice_packs:
        out.append(("voice_packs", "Download read aloud voices", step_voice_packs))
    if plan.pull_models:
        out.append(("pull_more", "Download " + ", ".join(plan.pull_models), step_pull_more))
    return out


def step_build(plan: Plan, profile: dict, report) -> str:
    from . import paths

    errors, _ = paths.check(profile)
    if errors:
        raise RuntimeError("path guard: " + "; ".join(errors))
    agents_build.build_all(profile)
    litellm_build.build(profile)
    winget_build.build()
    claude_env.write_settings_local(profile)
    # Claude Code in the checkout (and its worktrees) gets Claude's own keys instead of the stack's; the switch file
    # follows the profile before the services start.
    for path, result in claude_access.connect():
        if result.startswith("failed"):
            warn(f"{path}: {result}")
    claude_access.write_switch(profile)
    return f"primary model {profile['models'].get('primary')}, external models {'on' if profile['policy']['external']['enabled'] else 'off'}"


def step_web_filter(plan: Plan, profile: dict, report) -> str:
    """Blocked sites (stacklib/webfilter.py): download the lists, fill Open WebUI's web search filter when its database
    exists (a fresh one takes the filters from its environment at first start), write the Claude security audit's
    list, and say whether this PC uses protective DNS, which covers every app, Claude Desktop's browser included."""
    from . import webfilter

    if not webfilter.enabled(profile):
        raise Skip("not chosen; tick Blocked sites in the installer, or turn on Block unsafe sites in the tray's "
                   "Settings")
    report("downloading the lists of blocked sites")
    failed = [r.text for r in webfilter.maintain(profile) if not r.ok]
    text = f"{webfilter.summary(profile)} {webfilter.dns_text()}"
    if failed:
        raise Warn("; ".join(failed) + ". " + text)
    return text


def step_pull(plan: Plan, profile: dict, report) -> str:
    if not plan.pull:
        raise Skip("not chosen; run `uv run scripts/stack.py pull` later")
    base = _base(profile)
    if not ollama.version(base):
        raise RuntimeError(f"Ollama does not answer at {base}")
    models = models_to_pull(profile)
    failed = []
    for i, m in enumerate(models):
        def progress(frac, done, total, i=i, m=m):
            text = f"{m}: {done / 1e9:.1f} of {total / 1e9:.1f} GB" if total else f"{m}: starting"
            report(f"{text} (model {i + 1} of {len(models)})", (i + (frac or 0)) / len(models))
        info(f"ollama pull {m}")
        try:
            ollama.pull_stream(base, m, progress)
        except (RuntimeError, OSError, ValueError) as e:
            warn(f"{m}: {e}")
            failed.append(f"{m} ({e})")
    if failed:
        raise RuntimeError("could not download " + "; ".join(failed))
    return f"{len(models)} models in {plan.model_store}"


def step_start(plan: Plan, profile: dict, report) -> str:
    from . import startup

    try:
        lnk = startup.ensure_menu_shortcut()
    except Exception as e:  # noqa: BLE001 - start.cmd still works without the Start menu entry
        report(f"could not create the Start menu entry: {e}")
        lnk = None
    if not plan.start_stack:
        where = "the Start menu entry Agent Stack or start.cmd" if lnk else "start.cmd"
        raise Skip(f"not chosen; start it later with {where}")
    if startup.running_pid():
        if not plan.tool_dir:
            return "the tray app was already running"
        report("restarting the tray app so it finds the tools in their new folder")
        startup.stop_tray()
    state, msg = startup.launch_and_wait()
    if state == "failed":
        raise RuntimeError(msg)
    return f"tray app {msg}"


def step_links(plan: Plan, profile: dict, report) -> str:
    """Point what lives outside the app folder at this app: the start-at-login entry and scheduled tasks. Nothing in a
    closed-source app's config is written: the recordings server Claude Desktop ran is no longer set up, and Remove on
    the tray's Features card takes an old one off."""
    from . import deploy, startup, tasks

    notes, warns = [], []
    if not IS_WINDOWS and startup.is_installed():
        startup.install()   # Windows rewrites its .lnk in the Start step
        notes.append("start at login now starts this app")
    try:
        names = tasks.registered()
    except Exception:  # noqa: BLE001 - schtasks missing or refused: nothing registered to fix
        names = set()
    if IS_WINDOWS and names:
        here = os.path.normcase(str(REPO))
        names = {n for n in names
                 if here not in os.path.normcase(tasks._schtasks("/Query", "/XML", "/TN", tasks.TASK_FOLDER + n).stdout or "")}
    if names:
        warns.append(f"{len(names)} scheduled task(s) still start the services from the folder they were registered "
                     f"in; from an administrator terminal run `stack.py tasks install` with this app's Python "
                     f"({deploy.venv_python(REPO)}) to point them here")
    if not deploy.is_app():
        notes.append("set up inside this checkout (--here): it holds the logs, data and settings")
    if warns:
        raise Warn("; ".join(notes + warns))
    return "; ".join(notes) or "nothing outside the app folder to update"


STEPS = (
    ("secrets", "Create local secrets (.env)", step_secrets),
    ("disks", "Check this PC (drives, GPU, memory)", step_disks),
    ("ollama_install", "Install Ollama", step_ollama_install),
    ("models_move", "Move models already downloaded", step_models_move),
    ("ollama_env", "Point Ollama at the models folder", step_ollama_env),
    ("tools", "Install the gateway and the chosen Python tools", step_tools),
    ("build", "Generate gateway and agent configs", step_build),
    ("web_filter", "Set up blocked sites (web filter)", step_web_filter),
    ("pull", "Download models", step_pull),
    ("huggingface", "Set up the Hugging Face cache", step_huggingface),
    ("media", "Install ComfyUI and the image model", step_media),
    ("dictation", "Install voice typing (speech model)", step_dictation),
    ("read_aloud", "Install read aloud (Kokoro voices)", step_read_aloud),
    ("openclaw", "Install OpenClaw", step_openclaw),
    ("links", "Point start-up entries at this app", step_links),
    ("start", "Start the stack", step_start),
)


def run(plan: Plan, state_file: Path | None = None, steps=None) -> bool:
    """Run every step (plan_steps(plan) unless given); a failed step is recorded and the rest still run. True when
    none failed. The profile is read again before each step, so a step sees what the one before changed (a removal
    turns a feature off, and the tools step must not install it again)."""
    steps = plan_steps(plan) if steps is None else steps
    progress = Progress([(sid, title) for sid, title, _ in steps], state_file)
    for sid, _, fn in steps:
        progress.begin(sid)
        try:
            profile = prof.resolve_profile()
            detail = fn(plan, profile, lambda d=None, f=None, sid=sid: progress.update(sid, d, f))
            progress.end(sid, "done", detail or "")
        except Skip as e:
            progress.end(sid, "skipped", str(e))
        except Warn as e:
            progress.end(sid, "warning", str(e))
        except Exception as e:  # noqa: BLE001 - every failure is reported, then the next step runs
            traceback.print_exc()
            progress.end(sid, "failed", str(e) or type(e).__name__)
    return progress.finish()


# ---------------------------------------------------------------- background worker

def read_state() -> dict:
    """The worker's last recorded state; status "interrupted" when it says running but its process is gone."""
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if state.get("status") == "running" and services._proc_info(state.get("pid") or 0)[1] != state.get("started"):
        state["status"] = "interrupted"
    return state


def worker_running() -> bool:
    return read_state().get("status") == "running"


def _console_python() -> str:
    """python.exe next to pythonw.exe: the worker needs a (hidden) console that uv, winget and ollama can inherit.
    It runs as PAS-Installer.exe (procname) when sys.executable is a venv launcher the copy can be made from."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        exe = exe.parent / "python.exe"
    return str(procname.named(exe, "installer"))


def spawn_worker(plan: Plan) -> int:
    """Start `stack.py install --worker` outside this process, so closing the window or terminal does not stop it."""
    if worker_running():
        raise RuntimeError("setup is already running")
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    PLAN_FILE.write_text(json.dumps(asdict(plan), indent=1), encoding="utf-8")
    STATE_FILE.unlink(missing_ok=True)
    log = open(LOG_FILE, "wb")
    cmd = [_console_python(), str(REPO / "scripts" / "stack.py"), "install", "--worker", str(PLAN_FILE)]
    kwargs: dict = {"cwd": REPO, "stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL,
                    "env": {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}}
    try:
        if IS_WINDOWS:
            kwargs["creationflags"] = services.WINDOWS_FLAGS
            try:
                proc = subprocess.Popen(cmd, **kwargs)
            except PermissionError:   # the launching job forbids breakaway; setup then ends with that terminal
                kwargs["creationflags"] &= ~services.CREATE_BREAKAWAY_FROM_JOB
                proc = subprocess.Popen(cmd, **kwargs)
        else:
            proc = subprocess.Popen(cmd, start_new_session=True, **kwargs)
    finally:
        log.close()
    # Recorded at once, so a worker that dies before its first write reads as interrupted, not as starting forever.
    STATE_FILE.write_text(json.dumps({
        "status": "running", "pid": proc.pid, "started": services._proc_info(proc.pid)[1], "log": str(LOG_FILE),
        "steps": [{"id": i, "title": t, "status": "pending", "detail": "", "fraction": None} for i, t, _ in plan_steps(plan)],
        "remove": list(plan.remove), "targets": list(plan.targets),
    }), encoding="utf-8")
    return proc.pid


def tray_plan(profile: dict, **kw) -> Plan:
    """A plan for the tray: the profile's folders as they are, no drive check, no Hugging Face move, no Ollama
    restart and no tray start (the tray is running), and only the steps a change needs."""
    store = features.model_store(profile)
    base = dict(model_store=store, pull=False, restart_ollama=False, check_disks=False, setup_huggingface=False,
                setup_media=False, start_stack=False, only=[])
    base.update(kw)
    return Plan(**base)


def start_feature(profile: dict, fid: str, status: dict | None = None) -> int:
    """The tray's Install (or Repair) button: switch the feature on in machines/<HOST>.yaml, with what it runs inside,
    and run the steps that install it in the setup worker. Raises ValueError when it needs a folder the profile does
    not have yet (the installer asks for it). Returns the worker's pid."""
    if not features.BY_ID[fid].offered:
        raise ValueError(f"{features.BY_ID[fid].short} is no longer offered; it can only be removed")
    if worker_running():   # before the profile changes: a switch turned on with nothing installed reads as broken
        raise RuntimeError("setup is already running; try again when it has finished")
    status = features.statuses(profile) if status is None else status
    want = features.with_requirements({fid})
    if any(features.BY_ID[f].needs_media for f in want) and not (profile.get("media") or {}).get("root"):
        raise ValueError(f"{features.BY_ID[fid].short} needs a media folder; the installer asks for one")
    on = {f for f, s in status.items() if s.on or s.locked}
    save_features(profile, on | want, status=status)
    steps = sorted({s for f in want for s in FEATURE_STEPS.get(f, [])}, key=[s[0] for s in STEPS].index)
    plan = tray_plan(profile, only=steps, pull=fid == "models", targets=sorted(want), **{
        "setup_media": "images" in want,
        "install_openclaw": fid == "openclaw" and not (status.get("openclaw") and status["openclaw"].installed),
        "setup_openclaw": fid == "openclaw",
    })
    return spawn_worker(plan)


def start_removal(profile: dict, fids=(), models=()) -> int:
    """The tray's Remove buttons: remove features and delete Ollama models in the setup worker. Returns its pid."""
    targets = sorted(fids) + (["models"] if models else [])
    return spawn_worker(tray_plan(profile, remove=list(fids), remove_models=list(models), targets=targets))


def start_voice_packs(profile: dict, download=(), remove=()) -> int:
    """The tray's Download and Remove for read aloud voices, in the setup worker. Returns its pid."""
    return spawn_worker(tray_plan(profile, voice_packs=list(download), remove_voices=list(remove),
                                  targets=["read_aloud"]))


def start_download(profile: dict, models) -> int:
    """The tray's Download button for an Ollama model, in the setup worker. Returns its pid."""
    return spawn_worker(tray_plan(profile, pull_models=list(models), targets=["models"]))


def launch_window() -> int:
    """Open the installer window in a process of its own, as install.cmd does: the tray's Add features button runs
    this, and the window (and the setup worker it starts) must not depend on the tray. Returns the pid."""
    cmd = [_console_python(), str(REPO / "scripts" / "installer.py")]
    kwargs: dict = {"cwd": REPO, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                    "stderr": subprocess.DEVNULL, "env": {**os.environ, "AGENT_STACK_HIDE_CONSOLE": "1"}}
    if not IS_WINDOWS:
        return subprocess.Popen(cmd, start_new_session=True, **kwargs).pid
    kwargs["creationflags"] = services.WINDOWS_FLAGS
    try:
        return subprocess.Popen(cmd, **kwargs).pid
    except PermissionError:   # the tray's job forbids breakaway; the window then closes with the tray
        kwargs["creationflags"] &= ~services.CREATE_BREAKAWAY_FROM_JOB
        return subprocess.Popen(cmd, **kwargs).pid


def run_worker(plan_file: Path) -> bool:
    known = {f.name for f in fields(Plan)}
    plan = Plan(**{k: v for k, v in json.loads(Path(plan_file).read_text(encoding="utf-8")).items() if k in known})
    info(f"[install] {time.strftime('%Y-%m-%d %H:%M:%S')} pid {os.getpid()} plan {json.dumps(asdict(plan))}")
    return run(plan, STATE_FILE)


def summary(state: dict) -> str:
    return {
        "running": "Setup is running in the background.",
        "done": "Setup finished.",
        "warnings": "Setup finished with warnings.",
        "failed": "Setup finished with problems.",
        "interrupted": "Setup stopped before it finished (its process is gone).",
    }.get(state.get("status", ""), "Setup has not run yet.")
