"""Path guard (plan T08, decision D-M6): media tools and their caches stay inside the folders the owner allowed.

`agent_access.allowed_roots` in machines/<HOST>.yaml lists those folders. An empty list means "ask the owner": every
media path is refused until he fills it in. `model_store` and `OLLAMA_MODELS` predate the guard, so a path of theirs
outside the list is only a warning.
"""
from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath

from . import IS_WINDOWS


def _norm(path: str) -> str:
    """Absolute, normalised and case-folded on Windows. Symlinks and junctions are resolved when the path exists,
    so a link inside an allowed folder that points outside it is judged by its target."""
    p = Path(os.path.expandvars(os.path.expanduser(path)))
    try:
        p = p.resolve(strict=False)
    except OSError:
        p = Path(os.path.abspath(p))
    text = os.path.normpath(str(p))
    return text.lower() if IS_WINDOWS else text


def _is_absolute(path: str) -> bool:
    return Path(path).is_absolute() or (IS_WINDOWS and PureWindowsPath(path).is_absolute())


def inside(path: str, roots: list[str]) -> bool:
    """True when `path` is one of `roots` or below one. `..` segments are resolved first."""
    if not path or not _is_absolute(os.path.expanduser(path)):
        return False
    target = _norm(path)
    for root in roots or []:
        if not root:
            continue
        r = _norm(root)
        if target == r or target.startswith(r.rstrip("\\/") + os.sep):
            return True
    return False


def allowed_roots(profile: dict) -> list[str]:
    return [str(r) for r in ((profile.get("agent_access") or {}).get("allowed_roots") or []) if r]


def media_paths(profile: dict) -> dict[str, str]:
    """Every folder a media tool writes to, by name (the names appear in error messages)."""
    media = profile.get("media") or {}
    out: dict[str, str] = {}
    root = media.get("root") or ""
    if root:
        out["media.root"] = root
    for key in ("comfyui_dir", "models_dir", "output_dir", "input_dir", "uv_cache", "whisper_dir", "recordings_dir", "transcripts_dir"):
        if media.get(key):
            out[f"media.{key}"] = media[key]
    if media.get("hf_home"):
        out["media.hf_home"] = media["hf_home"]
    return out


def check(profile: dict) -> tuple[list[str], list[str]]:
    """(errors, warnings). Errors: a media path outside the allowed roots, or any media path while the list is
    empty. Warnings: the older Ollama model store outside the list."""
    roots = allowed_roots(profile)
    errors: list[str] = []
    warnings: list[str] = []
    wanted = media_paths(profile)
    if wanted and not roots:
        errors.append("agent_access.allowed_roots is empty, so no media folder is allowed yet: add the folders you "
                      f"choose to machines/{profile.get('name', '<HOST>')}.yaml (refused: {', '.join(wanted)})")
        return errors, warnings
    for name, path in wanted.items():
        if not inside(path, roots):
            errors.append(f"{name} = {path} is outside agent_access.allowed_roots ({'; '.join(roots)})")
    store = (profile.get("ollama_env") or {}).get("OLLAMA_MODELS") or profile.get("model_store") or ""
    if roots and store and not inside(store, roots):
        warnings.append(f"OLLAMA_MODELS = {store} is outside agent_access.allowed_roots (allowed: it predates the guard)")
    return errors, warnings


def require(profile: dict, path: str, what: str) -> str:
    """Return `path` when it is allowed, else raise PermissionError naming what wanted it."""
    roots = allowed_roots(profile)
    if not roots:
        raise PermissionError(f"{what}: agent_access.allowed_roots is empty; add the folder {path} to it first")
    if not inside(path, roots):
        raise PermissionError(f"{what}: {path} is outside agent_access.allowed_roots ({'; '.join(roots)})")
    return path
