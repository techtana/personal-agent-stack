"""Support library for scripts/stack.py (profile, generators, services, bench, smoke)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MACHINES_DIR = REPO / "machines"
AGENTS_DIR = REPO / "agents"
MEMORY_DIR = REPO / "memory"
TRACES_DIR = REPO / "traces"
INFRA_DIR = REPO / "infrastructure"
LITELLM_DIR = INFRA_DIR / "litellm"
ENV_FILE = REPO / ".env"
IS_WINDOWS = os.name == "nt"


def info(msg: str) -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print(f"WARN  {msg}", file=sys.stderr, flush=True)


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR {msg}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def load_dotenv(path: Path = ENV_FILE) -> dict[str, str]:
    """Minimal .env reader (KEY=value, # comments, optional quotes). Does not touch os.environ."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split(" #", 1)[0].strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        out[k.strip()] = v
    return out


def env_value(name: str, dotenv: dict[str, str] | None = None) -> str:
    """Process environment first, then .env."""
    if os.environ.get(name):
        return os.environ[name]
    dotenv = load_dotenv() if dotenv is None else dotenv
    return dotenv.get(name, "")


def which(name: str) -> str | None:
    """shutil.which plus the uv tools bin dir, which may not be on PATH in fresh shells."""
    import shutil

    found = shutil.which(name)
    if found:
        return found
    for cand in (Path.home() / ".local" / "bin" / name, Path.home() / ".local" / "bin" / f"{name}.exe"):
        if cand.exists():
            return str(cand)
    if IS_WINDOWS and name == "ollama":
        cand = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if cand.exists():
            return str(cand)
    if IS_WINDOWS and name == "claude":
        pkgs = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
        for d in pkgs.glob("Anthropic.ClaudeCode*") if pkgs.exists() else []:
            if (d / "claude.exe").exists():
                return str(d / "claude.exe")
    return None
