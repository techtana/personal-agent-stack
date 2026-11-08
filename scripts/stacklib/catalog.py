"""The installer's catalog, config/installer.yaml: what the stack can install, from where, in which version, how big it
is, and the choices the installer and Settings offer. Read once per process.

Every module that installs or estimates something takes its versions, URLs and model lists from here, so a new
version or model is a change to that file and not to code. This module imports PyYAML only when the file is first
read: the voice typing app imports it from its own environment, which has PyYAML too.
"""
from __future__ import annotations

import functools
from pathlib import Path

from . import REPO

CATALOG_FILE = REPO / "config" / "installer.yaml"


class CatalogError(RuntimeError):
    """config/installer.yaml is missing or does not parse."""


@functools.lru_cache(maxsize=1)
def load(path: Path | None = None) -> dict:
    import yaml

    path = path or CATALOG_FILE
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise CatalogError(f"could not read the installer catalog {path}: {e}") from e
    if not isinstance(data, dict):
        raise CatalogError(f"{path} is not a mapping")
    return data


def section(name: str) -> dict:
    return load().get(name) or {}


# ---------------------------------------------------------------- Ollama

def ollama() -> dict:
    return section("ollama")


def models() -> dict[str, dict]:
    """Ollama models: tag -> {size_gb, role, notes, measured}."""
    return {str(k): dict(v or {}) for k, v in (load().get("models") or {}).items()}


def measured_models() -> dict[tuple[str, int], tuple[float, float, int]]:
    """(model, context) -> (GPU GB, system-RAM GB, tokens/s), measured on the reference PC."""
    out = {}
    for name, m in models().items():
        for ctx, (vram, ram, speed) in (m.get("measured") or {}).items():
            out[(name, int(ctx))] = (float(vram), float(ram), int(speed))
    return out


def context_choices() -> list[int]:
    return [int(n) for n in load().get("context_choices") or (8192, 16384, 32768, 65536)]


# ---------------------------------------------------------------- Python tools

def python_tools() -> dict[str, dict]:
    """uv tools: id -> {env, script, install (arguments after the python), python}."""
    return {k: dict(v) for k, v in (load().get("python_tools") or {}).items()}


def tool(tool_id: str) -> dict:
    return python_tools()[tool_id]


# ---------------------------------------------------------------- images, Whisper, Kokoro, OpenClaw

def images() -> dict:
    return section("images")


def workflow(name: str) -> dict:
    return (images().get("workflows") or {}).get(name) or {}


def whisper() -> dict:
    return section("whisper")


def whisper_models() -> dict[str, dict]:
    """faster-whisper models offered: name -> {repo, download_gb, vram_gb, s_per_15s}, in the file's order."""
    return {str(k): dict(v) for k, v in (whisper().get("models") or {}).items()}


def whisper_repos() -> dict[str, str]:
    """Every faster-whisper name the stack knows -> its Hugging Face repository."""
    out = {name: m["repo"] for name, m in whisper_models().items() if m.get("repo")}
    out.update({str(k): str(v) for k, v in (whisper().get("other_repos") or {}).items()})
    return out


def kokoro() -> dict:
    return section("kokoro")


def openclaw() -> dict:
    return section("openclaw")


def version_tuple(text: str) -> tuple[int, int, int] | None:
    parts = [int(p) for p in str(text or "").strip().split(".")[:3] if p.isdigit()]
    return tuple((parts + [0, 0, 0])[:3]) if parts else None


def node_ranges() -> list[tuple[tuple[int, int, int], tuple[int, int, int] | None]]:
    """Node.js versions OpenClaw accepts: [(from, below or None)]."""
    out = []
    for lo, hi in openclaw().get("node_versions") or ():
        start = version_tuple(lo)
        if start:
            out.append((start, version_tuple(hi)))
    return out


def feature_footprint(fid: str) -> dict[str, float]:
    """A feature's own program on disk and in memory: disk_gb, ram_gb, ram_busy_gb, vram_gb, vram_busy_gb."""
    raw = (load().get("features") or {}).get(fid) or {}
    return {k: float(raw.get(k) or 0.0) for k in ("disk_gb", "ram_gb", "ram_busy_gb", "vram_gb", "vram_busy_gb")}
