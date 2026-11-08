"""Voice typing: speak instead of typing, into any app (Logseq, documents, browser text fields, Open WebUI).

A floating mic button and a global hotkey record the microphone; Whisper (faster-whisper) transcribes on this machine;
in polish mode the gateway's local model removes fillers and false starts before the text goes into the window that
had focus. Audio stays in memory, and the cleanup uses a private gateway alias, so nothing leaves the machine.

This module runs in the project environment (stack.py, the tray): settings, the service command and the installer.
The app itself (audio, VAD, Whisper, the button) runs in its own environment, built by install() under media.root,
because faster-whisper and its native libraries do not belong in the project venv. Design and measurements:
docs/design/plans/2026-11-07-voice-typing.md.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, fields
from pathlib import Path

from .. import IS_WINDOWS, REPO, info, warn, which

MODES = ("polish", "live")
STYLES = ("verbatim", "clean", "concise")
INSERTS = ("paste", "type")
DEVICES = ("auto", "cuda", "cpu")

# Versions that loaded under Smart App Control on SEKAIHOME (2026-11-07; Python 3.14 from python.org). Smart App
# Control judges compiled modules file by file, so a new version is a new judgement: test it in a throwaway venv first.
PACKAGES = (
    "faster-whisper==1.2.1",
    "ctranslate2==4.8.5",
    "onnxruntime==1.31.1",
    "av==17.0.0",          # 19.0.2 and 16.0.1 were refused in ComfyUI's venv (memory/lessons.md, 2026-11-04)
    "numpy==2.5.4",
    "tokenizers==0.23.3",
    "pyyaml>=6.0",
)
IMPORT_CHECK = ("import ctranslate2, onnxruntime, av, numpy, tokenizers, faster_whisper, yaml, tkinter; "
                "print(ctranslate2.__version__, ctranslate2.get_cuda_device_count())")


@dataclass
class Config:
    """The machine profile's `dictation:` section (machines/_defaults.yaml documents each key)."""
    hotkey: str = "ctrl+alt+d"
    mode: str = "polish"
    style: str = "clean"
    language: str = "auto"
    model: str = "large-v3-turbo"
    cpu_model: str = "small"
    device: str = "auto"
    compute_type: str = "auto"
    silence_stop_s: float = 3.0
    start_timeout_s: float = 8.0
    phrase_pause_s: float = 0.7
    max_minutes: float = 10.0
    insert: str = "paste"
    cleanup_model: str = "local-small"
    vocabulary: str = ""
    mic: str = ""
    unload_after_min: float = 30.0
    button: bool = True
    env_dir: str = ""

    @classmethod
    def from_profile(cls, profile: dict) -> "Config":
        raw = dict(profile.get("dictation") or {})
        cfg = cls()
        for f in fields(cls):
            if raw.get(f.name) is None:
                continue
            value = raw[f.name]
            try:
                if f.type in ("float", float):
                    value = float(value)
                elif f.type in ("bool", bool):
                    value = value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "on")
                else:
                    value = str(value).strip()
            except (TypeError, ValueError):
                warn(f"dictation.{f.name}: {value!r} is not valid; using {getattr(cfg, f.name)!r}")
                continue
            setattr(cfg, f.name, value)
        for name, allowed in (("mode", MODES), ("style", STYLES), ("insert", INSERTS), ("device", DEVICES)):
            if getattr(cfg, name) not in allowed:
                warn(f"dictation.{name}: {getattr(cfg, name)!r} is not one of {', '.join(allowed)}; using {getattr(cls, name)!r}")
                setattr(cfg, name, getattr(cls, name))
        from .models import valid_language

        cfg.language = cfg.language.lower() or "auto"
        if not valid_language(cfg.language):
            warn(f"dictation.language: {cfg.language!r} is not a Whisper language code; detecting the language instead")
            cfg.language = "auto"
        cfg.silence_stop_s = min(max(cfg.silence_stop_s, 0.8), 30.0)
        cfg.start_timeout_s = min(max(cfg.start_timeout_s, 2.0), 60.0)
        cfg.phrase_pause_s = min(max(cfg.phrase_pause_s, 0.3), 3.0)
        cfg.max_minutes = min(max(cfg.max_minutes, 0.5), 60.0)
        return cfg


# ---------------------------------------------------------------- folders

def env_dir(profile: dict) -> Path:
    """Where the app's Python environment lives: dictation.env_dir, else <media.root>/dictation (next to ComfyUI, inside
    the folders the owner allowed), else <data_dir>/dictation on a machine without a media folder."""
    cfg = Config.from_profile(profile)
    if cfg.env_dir:
        return Path(cfg.env_dir)
    root = (profile.get("media") or {}).get("root") or ""
    if root:
        return Path(root) / "dictation"
    return Path(profile.get("data_dir") or REPO / ".run") / "dictation"


def env_python(profile: dict, windowed: bool = False) -> Path:
    venv = env_dir(profile) / ".venv"
    if not IS_WINDOWS:
        return venv / "bin" / "python"
    windowless = venv / "Scripts" / "pythonw.exe"
    return windowless if windowed and windowless.exists() else venv / "Scripts" / "python.exe"


def installed(profile: dict) -> bool:
    venv = env_dir(profile) / ".venv"
    site = venv / "Lib" / "site-packages" if IS_WINDOWS else next(iter(sorted(venv.glob("lib/python*/site-packages"))), venv)
    return env_python(profile).exists() and (site / "faster_whisper" / "__init__.py").exists()


def state_dir(profile: dict) -> Path:
    """Button position and other per-machine runtime state (gitignored)."""
    return Path(profile.get("data_dir") or REPO / ".run") / "dictation"


def hf_home(profile: dict) -> str:
    return (profile.get("media") or {}).get("hf_home") or os.environ.get("HF_HOME", "")


def app_env(profile: dict, base_env: dict) -> dict:
    """Environment of the app process: scripts/ on the path for `-m stacklib.dictation`, the machine's name so it reads
    the same profile, and the Hugging Face cache the owner chose."""
    env = {**base_env, "PYTHONPATH": str(REPO / "scripts"), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
           "AGENT_STACK_MACHINE": profile.get("name") or ""}
    if hf_home(profile):
        env["HF_HOME"] = hf_home(profile)
    env.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    return env


def service_command(profile: dict, base_env: dict) -> dict | None:
    """Command, cwd and env for services.start(); None when voice typing is off in the profile."""
    if (profile.get("services") or {}).get("dictation") != "native":
        return None
    # -P keeps the working directory off sys.path; PYTHONPATH still adds scripts/ for the package.
    return {
        "cmd": [str(env_python(profile, windowed=True)), "-P", "-m", "stacklib.dictation", "run"],
        "cwd": str(REPO),
        "env": app_env(profile, base_env),
    }


def control_url(profile: dict) -> str:
    return f"http://127.0.0.1:{profile['ports']['dictation']}"


def hotkey_label(profile: dict) -> str:
    """'Ctrl+Alt+Space' for menus and help text."""
    return "+".join(part.strip().capitalize() for part in Config.from_profile(profile).hotkey.split("+"))


# ---------------------------------------------------------------- install

def _run(cmd: list, env: dict | None = None) -> None:
    info("  $ " + " ".join(str(c) for c in cmd))
    r = subprocess.run([str(c) for c in cmd], env=env, check=False)
    if r.returncode:
        raise RuntimeError(f"{Path(str(cmd[0])).name} exited with code {r.returncode}")


def model_cached(profile: dict, model: str) -> bool:
    """True when the faster-whisper model is already in the Hugging Face cache (or `model` is a local folder)."""
    if Path(model).is_dir():
        return True
    from .models import repo_for

    home = Path(hf_home(profile) or Path.home() / ".cache" / "huggingface")
    snaps = home / "hub" / f"models--{repo_for(model).replace('/', '--')}" / "snapshots"
    return any((s / "model.bin").exists() for s in snaps.glob("*")) if snaps.exists() else False


def install(profile: dict, report=lambda *a: None, download_model: bool = True) -> str:
    """Build the app's environment from a python.org Python (its signed launchers run under Smart App Control), install
    the pinned packages, check that every compiled module loads, and fetch the Whisper model into HF_HOME."""
    from .. import media, paths

    target = env_dir(profile)
    if (profile.get("media") or {}).get("root"):
        paths.require(profile, str(target), "voice typing environment")  # D-M6: media tools stay in allowed folders
    uv = which("uv") or "uv"
    env = {**os.environ, "UV_LINK_MODE": "hardlink"}
    m = profile.get("media") or {}
    if m.get("uv_cache"):
        env["UV_CACHE_DIR"] = m["uv_cache"]
    if hf_home(profile):
        env["HF_HOME"] = hf_home(profile)
    python = env_python(profile)
    if not python.exists():
        base = media.system_python()
        report(f"creating the voice typing environment in {target}")
        target.mkdir(parents=True, exist_ok=True)
        _run([uv, "venv", *(["--python", base] if base else []), target / ".venv"], env=env)
    report("installing faster-whisper and its libraries")
    _run([uv, "pip", "install", "--python", python, *PACKAGES], env=env)
    check = subprocess.run([str(python), "-c", IMPORT_CHECK], capture_output=True, text=True, check=False)
    if check.returncode:
        tail = (check.stderr or "").strip().splitlines()[-1:] or ["no output"]
        hint = " Smart App Control refused a DLL; see CodeIntegrity event 3033 for the file." if "Application Control" in tail[0] else ""
        raise RuntimeError(f"the voice typing environment does not import ({tail[0]}).{hint}")
    ct2, cuda = (check.stdout.split() + ["?", "0"])[:2]
    notes = [f"faster-whisper with CTranslate2 {ct2}"]
    if IS_WINDOWS and cuda != "0":
        from .gpu import cublas_dirs

        if cublas_dirs(target / ".venv"):
            notes.append("GPU ready (cuBLAS 12 found)")
        else:
            report("installing NVIDIA cuBLAS 12 for the GPU (about 0.5 GB)")
            _run([uv, "pip", "install", "--python", python, "nvidia-cublas-cu12"], env=env)
            notes.append("GPU libraries installed (nvidia-cublas-cu12)")
    cfg = Config.from_profile(profile)
    if download_model and not model_cached(profile, cfg.model):
        report(f"downloading the Whisper model {cfg.model} into {hf_home(profile) or 'the Hugging Face cache'}")
        code = f"import faster_whisper; print(faster_whisper.download_model({cfg.model!r}))"
        _run([python, "-c", code], env=app_env(profile, env))
        notes.append(f"downloaded {cfg.model}")
    elif download_model:
        notes.append(f"model {cfg.model} already cached")
    return "; ".join(notes)


def save_setting(profile: dict, key: str, value) -> None:
    """Write dictation.<key> into machines/<HOST>.yaml, keeping the owner's comments, so a choice made in the button's
    menu survives a restart and shows in the tray's Settings tab."""
    import yaml

    from .. import profile as prof
    from ..yamledit import set_key

    path = prof.machine_file(profile.get("name"))
    text = set_key(path.read_text(encoding="utf-8"), "dictation", key, value)
    if ((yaml.safe_load(text) or {}).get("dictation") or {}).get(key) != value:
        raise ValueError(f"could not write dictation.{key} into {path.name} safely")
    path.write_text(text, encoding="utf-8", newline="\n")


def write_state(profile: dict, **values) -> None:
    """Merge values into .run/dictation/state.json (button position, hidden flag)."""
    path = state_dir(profile) / "state.json"
    state = read_state(profile)
    state.update(values)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def read_state(profile: dict) -> dict:
    try:
        return json.loads((state_dir(profile) / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
