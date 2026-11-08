"""Local Whisper for recordings: a faster-whisper venv under media.whisper_dir and an MCP server for Claude Desktop.

The server (scripts/whisper_mcp.py) is copied next to the venv, so the Claude Desktop entry does not point into a git
checkout or worktree. It reads only below agent_access.allowed_roots (decision D-M6) and writes transcripts to
media.transcripts_dir. Audio stays local; a cloud client (Cowork, Claude Code profile A) receives the transcript text.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from . import IS_WINDOWS, REPO, info, which
from . import paths, procname, usage_log
from .media import _run, _uv_env, media, system_python

SERVER_SRC = REPO / "scripts" / "whisper_mcp.py"
SERVER_NAME = "local-whisper"
# Smart App Control allowed PyAV 17.0.0 in ComfyUI's cp314 venv and refused 19.0.2 and 16.0.1 (2026-11-04).
PACKAGES = ("faster-whisper", "av==17.0.0", "fastmcp==4.1.3", "nvidia-cublas-cu12", "nvidia-cudnn-cu12>=9,<10")
IMPORT_CHECK = ("import av, av.audio.frame, ctranslate2, faster_whisper, onnxruntime, numpy, tokenizers, fastmcp; "
                "print(ctranslate2.__version__, ctranslate2.get_cuda_device_count())")


def whisper_dir(profile: dict) -> Path:
    return Path(media(profile)["whisper_dir"])


def whisper_python(profile: dict) -> Path:
    d = whisper_dir(profile) / ".venv"
    return d / "Scripts" / "python.exe" if IS_WINDOWS else d / "bin" / "python"


def server_env(profile: dict) -> dict[str, str]:
    m = media(profile)
    env = {
        "WHISPER_ROOTS": os.pathsep.join(paths.allowed_roots(profile)),
        "WHISPER_RECORDINGS": m["recordings_dir"],
        "WHISPER_TRANSCRIPTS": m["transcripts_dir"],
        "WHISPER_MODEL": m.get("whisper_model") or "large-v3-turbo",
        "WHISPER_COMPUTE": m.get("whisper_compute") or "int8_float16",
        "WHISPER_CPU_MODEL": m.get("whisper_cpu_model") or "small",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        # One usage record per transcription into this checkout's traces/usage, for the tray's Usage tab.
        **usage_log.env_for(profile),
        "AGENT_STACK_CLIENT": "Claude Desktop",
    }
    if m.get("hf_home"):
        env["HF_HOME"] = m["hf_home"]
    return env


def server_entry(profile: dict) -> dict:
    """The mcpServers entry, in Claude Desktop's format (Claude Code's .mcp.json takes the same stdio shape)."""
    # Claude Desktop starts it as PAS-Recordings.exe (procname) when the copy can be made.
    return {"command": str(procname.named(whisper_python(profile), "recordings")), "args": ["-I", str(whisper_dir(profile) / "whisper_mcp.py")],
            "env": server_env(profile)}


def guarded(profile: dict) -> None:
    m = media(profile)
    roots = paths.allowed_roots(profile)
    for key in ("whisper_dir", "recordings_dir", "transcripts_dir"):
        if not m.get(key) or not paths.inside(m[key], roots):
            raise RuntimeError(f"media.{key} ({m.get(key) or 'unset'}) is not inside agent_access.allowed_roots {roots}")


def install(profile: dict, report=info) -> str:
    """Build the venv, install faster-whisper with CUDA 12 runtime wheels, copy the server, download the model."""
    guarded(profile)
    m = media(profile)
    target = whisper_dir(profile)
    uv = which("uv") or "uv"
    env = _uv_env(profile)
    python = whisper_python(profile)
    if not python.exists():
        base = system_python()
        report(f"creating Whisper's Python environment in {target}")
        target.mkdir(parents=True, exist_ok=True)
        _run([uv, "venv", *(["--python", base] if base else []), target / ".venv"], env=env)
    report("installing faster-whisper, cuBLAS and cuDNN (about 1.5 GB)")
    _run([uv, "pip", "install", "--python", python, *PACKAGES], env=env)
    check = subprocess.run([python, "-I", "-c", IMPORT_CHECK], capture_output=True, text=True, check=False)
    if check.returncode:
        tail = (check.stderr or "").strip().splitlines()[-1:] or ["no output"]
        raise RuntimeError(f"Whisper's environment does not import ({tail[0]})")
    shutil.copy2(SERVER_SRC, target / "whisper_mcp.py")
    for key in ("recordings_dir", "transcripts_dir"):
        Path(m[key]).mkdir(parents=True, exist_ok=True)
    report(f"downloading {m.get('whisper_model') or 'large-v3-turbo'} into the Hugging Face cache")
    dl = ("import faster_whisper.utils as u, sys; print(u.download_model(sys.argv[1]))")
    _run([python, "-I", "-c", dl, m.get("whisper_model") or "large-v3-turbo"], env={**os.environ, **server_env(profile)})
    ct2, gpus = check.stdout.split()
    return f"faster-whisper ready (ctranslate2 {ct2}, {gpus} CUDA device(s)); server at {target / 'whisper_mcp.py'}"


# ---------------------------------------------------------------- Claude Desktop (Chat, Cowork)

def desktop_config_path() -> Path:
    if IS_WINDOWS:
        return Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    if os.uname().sysname == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def register_desktop(profile: dict, config: Path | None = None) -> str:
    """Add or update the local-whisper entry; other servers and settings are kept. Backs the file up first."""
    config = config or desktop_config_path()
    data = {}
    if config.exists():
        text = config.read_text(encoding="utf-8")
        data = json.loads(text) if text.strip() else {}
        entry = server_entry(profile)
        if (data.get("mcpServers") or {}).get(SERVER_NAME) == entry:
            return f"{config}: {SERVER_NAME} already up to date"
        backup = config.with_name(f"{config.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(config, backup)
    else:
        config.parent.mkdir(parents=True, exist_ok=True)
        backup = None
    data.setdefault("mcpServers", {})[SERVER_NAME] = server_entry(profile)
    config.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return f"{config}: {SERVER_NAME} registered" + (f" (backup {backup.name})" if backup else "") + \
        "; quit Claude Desktop from the tray icon and reopen it to load the server"


def unregister_desktop(config: Path | None = None) -> str:
    config = config or desktop_config_path()
    if not config.exists():
        return f"{config} does not exist"
    data = json.loads(config.read_text(encoding="utf-8") or "{}")
    if SERVER_NAME not in (data.get("mcpServers") or {}):
        return f"{config}: {SERVER_NAME} not registered"
    shutil.copy2(config, config.with_name(f"{config.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}"))
    del data["mcpServers"][SERVER_NAME]
    config.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return f"{config}: {SERVER_NAME} removed"
