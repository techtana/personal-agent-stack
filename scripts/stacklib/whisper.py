"""What is left of the recordings feature: where an old install lives and how to take it off Claude Desktop.

Recordings put a faster-whisper venv and an MCP server (scripts/whisper_mcp.py, copied next to the venv) under
media.whisper_dir and registered the server in Claude Desktop's config. Claude Desktop is closed source, and the stack
keeps no ties to such apps, so it is no longer installed or registered. Remove on the tray's Features card (and
`stack.py whisper unregister`) take an old install off; stacklib/uninstall.py uses the helpers here. The server's code
stays in scripts/, because the usage records it wrote are still read by the Usage tab.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from . import IS_WINDOWS, REPO
from .media import media

SERVER_SRC = REPO / "scripts" / "whisper_mcp.py"
SERVER_NAME = "local-whisper"


def whisper_dir(profile: dict) -> Path:
    return Path(media(profile)["whisper_dir"])


def whisper_python(profile: dict) -> Path:
    d = whisper_dir(profile) / ".venv"
    return d / "Scripts" / "python.exe" if IS_WINDOWS else d / "bin" / "python"


# ---------------------------------------------------------------- Claude Desktop (Chat, Cowork)

def desktop_config_path() -> Path:
    if IS_WINDOWS:
        return Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    if os.uname().sysname == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _read_config(config: Path) -> dict:
    """Claude Desktop's config; utf-8-sig, since an editor may have saved it with a byte order mark."""
    text = config.read_text(encoding="utf-8-sig")
    return json.loads(text) if text.strip() else {}


def _write_config(config: Path, data: dict) -> None:
    """Write the config whole or not at all (a temporary file, then a rename), with LF line ends."""
    tmp = config.with_name(config.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, config)


def unregister_desktop(config: Path | None = None) -> str:
    config = config or desktop_config_path()
    if not config.exists():
        return f"{config} does not exist"
    data = _read_config(config)
    if SERVER_NAME not in (data.get("mcpServers") or {}):
        return f"{config}: {SERVER_NAME} not registered"
    shutil.copy2(config, config.with_name(f"{config.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}"))
    del data["mcpServers"][SERVER_NAME]
    _write_config(config, data)
    return f"{config}: {SERVER_NAME} removed"
