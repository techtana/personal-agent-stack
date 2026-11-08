"""Voice typing: speak instead of typing, into any app (Logseq, documents, browser text fields, Open WebUI).

A floating mic button and a global hotkey record the microphone; Whisper (faster-whisper) transcribes on this machine;
in polish mode the gateway's local model removes fillers and false starts before the text goes into the window that
had focus. Audio stays in memory, and the cleanup uses a private gateway alias, so nothing leaves the machine. The same
app refines selected text (refine.py) and, when read aloud is installed and on (read_aloud.enabled), reads it aloud
with Kokoro or a Windows voice (speak.py, tts.py).

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

# Versions that loaded under Smart App Control on the reference machine (2026-11-07; Python 3.14 from python.org). Smart App
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
# Read aloud, an optional feature installed into the same environment (install_read_aloud). Kokoro runs on the
# onnxruntime and numpy above; these two add espeak-ng's phonemes and Windows' own voices.
READ_PACKAGES = (
    "espeakng-loader==0.2.4",   # espeak-ng 1.52 (DLL and data, GPL-3.0); loaded under Smart App Control 2026-11-08
    "comtypes==1.4.17",         # pure Python COM, for Windows' own voices (SAPI)
)
# Read aloud on the GPU (read_aloud.device gpu, or auto on a PC with an NVIDIA card): onnxruntime-gpu in place of
# onnxruntime, built for CUDA 13, and cuDNN 9 for CUDA 13 without its dependencies (cuBLAS 13 and the CUDA runtime come
# from Ollama's lib/ollama/cuda_v13). About 0.8 GB. Measured 2026-11-08: 12-20x real time on an RTX 3060, 1.0 GB VRAM.
READ_GPU_PACKAGES = ("onnxruntime-gpu==1.31.1", "nvidia-cudnn-cu13==9.28.1.4")
READ_GPU_CHECK = ("import onnxruntime, sys; from stacklib.dictation import gpu; "
                  "ok = 'CUDAExecutionProvider' in onnxruntime.get_available_providers() and gpu.add_kokoro_cuda_dlls(); "
                  "print('cuda' if ok else 'missing'); sys.exit(0 if ok else 3)")
# Loads espeak-ng's DLL too: Smart App Control judges a DLL when it loads, not when the package installs.
READ_CHECK = ("import ctypes, comtypes, espeakng_loader, onnxruntime, numpy; "
              "ctypes.cdll.LoadLibrary(espeakng_loader.get_library_path()); print('ok')")


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
    cleanup_prompt: str = ""      # '' = cleanup.DEFAULT_PROMPT
    vocabulary: str = ""
    mic: str = ""
    unload_after_min: float = 30.0
    button: bool = True
    keep_minutes: float = 30.0    # how long the voice typing history keeps what you said and what was typed
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
        cfg.keep_minutes = min(max(cfg.keep_minutes, 1.0), 43200.0)   # a minute to 30 days
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
    the same profile, where its Whisper calls are recorded for the Usage tab, and the Hugging Face cache the owner
    chose."""
    from .. import usage_log

    env = {**base_env, "PYTHONPATH": str(REPO / "scripts"), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
           "AGENT_STACK_MACHINE": profile.get("name") or "", **usage_log.env_for(profile)}
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


def transcription_url(profile: dict) -> str:
    """Base URL of voice typing's OpenAI-compatible speech to text (POST <url>/audio/transcriptions), for Open WebUI's
    microphone. Built from the port alone, so it can only point at this machine."""
    port = int(profile["ports"]["dictation"])
    if not 0 < port < 65536:
        raise ValueError(f"ports.dictation {port} is not a TCP port")
    return f"http://127.0.0.1:{port}/v1"


KEY_NAME = "DICTATION_BEARER"


def api_key() -> str:
    """The key callers of the transcription endpoint send (Open WebUI): DICTATION_BEARER from the environment or .env.
    Its own key, not the gateway's: while voice typing is off, any local program could listen on its port and would
    learn only this one."""
    from .. import env_value

    return env_value(KEY_NAME)


def ensure_api_key(path: Path | None = None) -> str:
    """DICTATION_BEARER, appended to .env as a new random key when it is not set yet; the rest of .env is left as it
    is (comments included). The running voice typing app reads it on its next request."""
    import secrets

    from .. import ENV_FILE, load_dotenv

    path = path or ENV_FILE
    key = os.environ.get(KEY_NAME) or load_dotenv(path).get(KEY_NAME, "")
    if key:
        return key
    key = secrets.token_urlsafe(32)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(("" if not text or text.endswith("\n") else "\n") + f"{KEY_NAME}={key}\n")
    info(f"{path.name}: added {KEY_NAME}, the key Open WebUI's microphone uses with voice typing")
    return key


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
    # Read aloud's GPU option replaced onnxruntime with onnxruntime-gpu (same module, CPU included): keep it.
    packages = [READ_GPU_PACKAGES[0] if pkg.startswith("onnxruntime==") and read_aloud_gpu_installed(profile) else pkg
                for pkg in PACKAGES]
    _run([uv, "pip", "install", "--python", python, *packages], env=env)
    if packages != list(PACKAGES):
        _restore_gpu_runtime(profile, uv, python, env, report)   # faster-whisper pulled the CPU build back in
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


# ---------------------------------------------------------------- read aloud (optional, in the same environment)

def _site_packages(profile: dict) -> Path:
    venv = env_dir(profile) / ".venv"
    return venv / "Lib" / "site-packages" if IS_WINDOWS else next(iter(sorted(venv.glob("lib/python*/site-packages"))), venv)


def kokoro_cached(profile: dict, variant: str = "fp32") -> bool:
    """Kokoro's weights, tokenizer and default voice are in the Hugging Face cache (the pinned revision)."""
    from .speak import KOKORO_FILES, KOKORO_REPO, KOKORO_REVISION

    if variant not in KOKORO_FILES:
        return True   # off: Windows voices only, nothing to download
    home = Path(hf_home(profile) or Path.home() / ".cache" / "huggingface")
    snap = home / "hub" / f"models--{KOKORO_REPO.replace('/', '--')}" / "snapshots" / KOKORO_REVISION
    return all((snap / name).exists() for name in (KOKORO_FILES[variant], "tokenizer.json", "voices/af_heart.bin"))


def read_aloud_installed(profile: dict) -> bool:
    """Read aloud's packages are in voice typing's environment, and Kokoro's files are downloaded unless
    read_aloud.kokoro is off."""
    from .speak import Config as ReadConfig

    site = _site_packages(profile)
    packages = all((site / pkg / "__init__.py").exists() for pkg in ("espeakng_loader", "comtypes"))
    if not installed(profile) or not packages:
        return False
    return kokoro_cached(profile, ReadConfig.from_profile(profile).kokoro)


def _cpu_runtime(site: Path) -> bool:
    return any(site.glob("onnxruntime-*.dist-info"))


def read_aloud_gpu_installed(profile: dict) -> bool:
    """onnxruntime-gpu and cuDNN are in voice typing's environment (read aloud's GPU option), and the CPU build is not
    there beside it: both install into the same onnxruntime folder, and whichever came last owns the files."""
    site = _site_packages(profile)
    return (any(site.glob("onnxruntime_gpu-*.dist-info")) and not _cpu_runtime(site)
            and (site / "nvidia" / "cudnn" / "bin" / "cudnn64_9.dll").exists())


def _restore_gpu_runtime(profile: dict, uv: str, python: Path, env: dict, report) -> None:
    """Put onnxruntime-gpu's files back after something installed the CPU onnxruntime over them. faster-whisper
    depends on `onnxruntime`, which onnxruntime-gpu does not satisfy, so every voice typing install pulls the CPU
    build in again (seen on the reference machine, 2026-11-08: both installed, CUDA gone)."""
    site = _site_packages(profile)
    if not _cpu_runtime(site):
        return
    report("putting ONNX Runtime for CUDA back (the CPU build was installed over it)")
    _run([uv, "pip", "uninstall", "--python", python, "onnxruntime"], env=env)
    _run([uv, "pip", "install", "--python", python, "--reinstall", "--no-deps", READ_GPU_PACKAGES[0]], env=env)


def wants_gpu(profile: dict) -> bool:
    """read_aloud.device gpu, or auto on a PC with an NVIDIA card (nvidia-smi, or the GPU `stack.py doctor` saw)."""
    from .speak import Config as ReadConfig

    device = ReadConfig.from_profile(profile).device
    if device != "auto":
        return device == "gpu"
    return bool(which("nvidia-smi")) or float((profile.get("detected") or {}).get("vram_mib") or 0) > 0


def _install_gpu(profile: dict, uv: str, python: Path, env: dict, report) -> str:
    """Swap onnxruntime for onnxruntime-gpu and add cuDNN 9, with voice typing stopped while its DLLs are replaced
    (Windows keeps a loaded DLL locked), then start it again if it was running."""
    from .. import services

    was_up = bool(next((r for r in services.status(profile) if r["service"] == "dictation"), {}).get("healthy"))
    if was_up:
        report("stopping voice typing while its ONNX Runtime is replaced")
        services.stop(profile, ["dictation"])
    try:
        report("installing ONNX Runtime for CUDA and cuDNN 9 (about 0.8 GB) for read aloud on the GPU")
        site = _site_packages(profile)
        if _cpu_runtime(site):
            _run([uv, "pip", "uninstall", "--python", python, "onnxruntime"], env=env)
        _run([uv, "pip", "install", "--python", python, "--reinstall", READ_GPU_PACKAGES[0]], env=env)
        _run([uv, "pip", "install", "--python", python, "--no-deps", READ_GPU_PACKAGES[1]], env=env)
    finally:
        if was_up:
            services.start(profile, ["dictation"])
    check = subprocess.run([str(python), "-P", "-c", READ_GPU_CHECK], capture_output=True, text=True, check=False,
                           env=app_env(profile, env))
    if check.returncode:
        return ("GPU libraries installed, but CUDA did not start here (Ollama's lib/ollama/cuda_v13 is needed); "
                "Kokoro runs on the CPU")
    return "Kokoro can run on the GPU (CUDA)"


def install_read_aloud(profile: dict, report=lambda *a: None) -> str:
    """Add read aloud to voice typing's environment: espeak-ng and comtypes, a check that espeak-ng's DLL loads, the
    GPU libraries when wants_gpu() (about 0.8 GB), and Kokoro's weights and voices in the Hugging Face cache (about
    0.35 GB for fp32; nothing with read_aloud.kokoro off)."""
    from .speak import Config as ReadConfig

    if not installed(profile):
        raise RuntimeError("voice typing is not installed; read aloud runs in its app (`stack.py dictate install`)")
    uv = which("uv") or "uv"
    env = {**os.environ, "UV_LINK_MODE": "hardlink"}
    m = profile.get("media") or {}
    if m.get("uv_cache"):
        env["UV_CACHE_DIR"] = m["uv_cache"]
    python = env_python(profile)
    report("installing espeak-ng and comtypes for read aloud")
    _run([uv, "pip", "install", "--python", python, *READ_PACKAGES], env=env)
    check = subprocess.run([str(python), "-c", READ_CHECK], capture_output=True, text=True, check=False)
    if check.returncode:
        tail = (check.stderr or "").strip().splitlines()[-1:] or ["no output"]
        refused = "Application Control" in tail[0] or "4551" in tail[0]
        hint = " Smart App Control refused a DLL; see CodeIntegrity event 3033 for the file." if refused else ""
        raise RuntimeError(f"read aloud's packages do not load ({tail[0]}).{hint}")
    notes = ["espeak-ng and comtypes installed"]
    variant = ReadConfig.from_profile(profile).kokoro
    if variant == "fp32" and wants_gpu(profile):
        notes.append("GPU libraries already installed" if read_aloud_gpu_installed(profile)
                     else _install_gpu(profile, uv, python, env, report))
    if variant == "off":
        notes.append("Kokoro is off (read_aloud.kokoro): Windows voices only")
    elif kokoro_cached(profile, variant):
        notes.append(f"Kokoro {variant} already downloaded")
    else:
        report(f"downloading Kokoro-82M ({variant}) and its voices into {hf_home(profile) or 'the Hugging Face cache'}")
        _run([python, "-P", "-m", "stacklib.dictation", "speak", "--download"], env=app_env(profile, env))
        notes.append(f"downloaded Kokoro {variant} and its voices")
    return "; ".join(notes)


def save_setting(profile: dict, key: str, value, section: str = "dictation") -> None:
    """Write <section>.<key> (dictation, refine or read_aloud) into machines/<HOST>.yaml, keeping the owner's comments,
    so a choice made in a button's menu survives a restart and shows in the tray's Settings tab."""
    import yaml

    from .. import profile as prof
    from ..yamledit import set_key

    path = prof.machine_file(profile.get("name"))
    text = set_key(path.read_text(encoding="utf-8"), section, key, value)
    if ((yaml.safe_load(text) or {}).get(section) or {}).get(key) != value:
        raise ValueError(f"could not write {section}.{key} into {path.name} safely")
    path.write_text(text, encoding="utf-8", newline="\n")


REFINE_TEMPLATE = """
refine:
  # Refine selected text: the pencil button next to the mic, or its hotkey. Your own styles go under prompts; they
  # appear in the button's right-click menu the next time you open it. An entry with a built-in id (polish, grammar,
  # concise, professional, friendly, simple, bullets) replaces that style's instructions.
  prompts:
    # my-voice: Rewrite in my voice. Short sentences, active verbs, no jargon.
    # email-reply:
    #   name: Email reply
    #   prompt: Turn my notes into a short, polite email reply. Keep every fact and date.
"""


def ensure_refine_section(path: Path) -> bool:
    """Append a commented `refine:` section with example styles when the machine file has none. True if it wrote."""
    import re

    import yaml

    text = path.read_text(encoding="utf-8")
    if re.search(r"^refine:", text, re.M):
        return False
    new = text.rstrip("\n") + "\n" + REFINE_TEMPLATE
    yaml.safe_load(new)  # never leave a file that no longer parses
    path.write_text(new, encoding="utf-8", newline="\n")
    return True


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
