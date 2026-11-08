"""The Logseq refine plugin (integrations/logseq-refine): build it, hand it its key, and say how it stands.

The plugin adds "Refine with <style>" to the right-click menu of a Logseq block (Logseq 2.x, database graphs). It sends
the block's text to voice typing's /plugin/ routes (stacklib/dictation/pluginapi.py) with REFINE_BEARER and writes the
suggestion back, so it needs voice typing running. Building needs Node.js: `npm ci` installs @logseq/libs at the
version pinned in package-lock.json, and build.mjs copies the plugin and that library into dist/.

Logseq loads the folder itself: Settings > Advanced > Developer mode on, then Plugins > Load unpacked plugin. This
module never writes Logseq's files; it only reads ~/.logseq/preferences.json to tell whether the folder is loaded.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from . import IS_WINDOWS, REPO, which
from .clients import ClientStatus

PLUGIN_DIR = REPO / "integrations" / "logseq-refine"
DIST = PLUGIN_DIR / "dist"
PLUGIN_ID = "agent-stack-refine"
LOAD_STEPS = ("In Logseq: Settings > Advanced > Developer mode on; then Settings > Plugins > Load unpacked plugin and "
              f"choose {PLUGIN_DIR}. Open the plugin's settings and paste the key.")


def built() -> bool:
    return (DIST / "index.html").is_file() and (DIST / "lsplugin.user.js").is_file()


def build(report=lambda msg: None, timeout: float = 600.0) -> str:
    """npm ci (or npm install when there is no lock file) and npm run build in the plugin folder."""
    npm = which("npm") or ""
    if not npm:
        raise RuntimeError("npm was not found; install Node.js LTS (winget install OpenJS.NodeJS.LTS) and try again")
    install = ["ci"] if (PLUGIN_DIR / "package-lock.json").is_file() else ["install"]
    for args, what in ((install + ["--ignore-scripts", "--no-audit", "--no-fund"], "installing @logseq/libs"),
                       (["run", "build"], "building the plugin")):
        report(what)
        r = subprocess.run([npm, *args], cwd=PLUGIN_DIR, capture_output=True, text=True, timeout=timeout,
                           check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0)
        if r.returncode:
            tail = ((r.stderr or "") + (r.stdout or "")).strip().splitlines()[-1:] or ["no output"]
            raise RuntimeError(f"npm {' '.join(args[:2])} failed: {tail[0]}")
    if not built():
        raise RuntimeError(f"the build left no plugin in {DIST}")
    return f"built {DIST}"


def logseq_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home()) / ".logseq"


def loaded_in_logseq(home: Path | None = None) -> bool | None:
    """True when Logseq's list of unpacked plugins names this folder, False when it does not, None when this machine has
    no Logseq preferences file. Read only."""
    prefs = (home or logseq_home()) / "preferences.json"
    try:
        data = json.loads(prefs.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return False
    want = os.path.normcase(os.path.normpath(str(PLUGIN_DIR)))
    externals = data.get("externals") if isinstance(data, dict) else None
    return any(isinstance(p, str) and os.path.normcase(os.path.normpath(p)) == want for p in externals or [])


CLEAR_AFTER_S = 60.0  # the tray empties the clipboard after this long, unless something else was copied meanwhile


def copy_to_clipboard(text: str) -> int:
    """Put text on the clipboard; 0 when that failed. On Windows through voice typing's Win32 helper, which keeps it
    out of Win+V clipboard history and cloud clipboard (Tk's clipboard crashes Python 3.14.7 there), and returns the
    clipboard's sequence number for clear_clipboard_if; elsewhere through the system's own tool, returning 1."""
    if IS_WINDOWS:
        try:
            from .dictation import winsys

            return winsys.Clipboard().set_text(text, hide=True) or 1
        except (OSError, MemoryError, ImportError, AttributeError):
            return 0
    if shutil.which("pbcopy"):
        cmd = ["pbcopy"]
    elif shutil.which("wl-copy"):
        cmd = ["wl-copy"]
    elif shutil.which("xclip"):
        cmd = ["xclip", "-selection", "clipboard"]
    else:
        return 0
    try:
        r = subprocess.run(cmd, input=text.encode("utf-8"), timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return 0
    return 1 if r.returncode == 0 else 0


def clear_clipboard_if(sequence: int) -> bool:
    """Empty the clipboard if it still holds what copy_to_clipboard put there (Windows; nothing copied since)."""
    if not IS_WINDOWS or sequence <= 1:
        return False
    try:
        from .dictation import winsys

        if winsys.sequence() != sequence:
            return False
        winsys.Clipboard().restore([])  # opens, empties, closes
        return True
    except (OSError, MemoryError, ImportError, AttributeError):
        return False


def status(home: Path | None = None) -> ClientStatus:
    from .dictation import refine_key

    if not built():
        return ClientStatus("off", "Not built", "Refine a Logseq block from its right-click menu. Set up builds it "
                                                "(needs Node.js), or `uv run scripts/stack.py logseq-plugin`.")
    if not refine_key():
        return ClientStatus("warn", "No key", "Set up adds REFINE_BEARER to .env and copies it for the plugin's "
                                              "settings.")
    loaded = loaded_in_logseq(home)
    if loaded:
        return ClientStatus("ok", "Loaded in Logseq", "Right-click a block's bullet > Refine with... Needs voice "
                                                      "typing running. Copy key puts the key on the clipboard again.")
    return ClientStatus("off", "Built", LOAD_STEPS + " Copy key puts it on the clipboard.")


def setup(report=lambda msg: None, rebuild: bool = False) -> tuple[str, int]:
    """Build the plugin if needed, make sure REFINE_BEARER exists, and copy it to the clipboard. Returns what to do
    next and copy_to_clipboard's result (for clear_clipboard_if)."""
    from .dictation import ensure_refine_key

    if rebuild or not built():
        report(build(report))
    key = ensure_refine_key()
    copied = copy_to_clipboard(key)
    where = ("The key is on the clipboard (kept out of clipboard history); paste it, then copy something else."
             if copied else "Copy REFINE_BEARER from .env.")
    return f"{LOAD_STEPS} {where}", copied
