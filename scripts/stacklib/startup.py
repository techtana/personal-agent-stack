"""Tray app launch helpers: detached launch, start-at-login entry, single instance."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from . import IS_WINDOWS, REPO, info
from . import services

TRAY_SCRIPT = REPO / "scripts" / "tray.py"
SHORTCUT_NAME = "Agent Stack.lnk"
PIDFILE = REPO / ".run" / "pids" / "tray.pid"
TRAY_LOG = REPO / ".run" / "logs" / "tray.log"
SHOW_REQUEST = REPO / ".run" / "tray.show"  # a second launch with --show leaves this for the running tray
# Lines the tray writes to its log (READY and FAILED in scripts/tray.py; keep the two in step).
TRAY_READY = "[tray] ready"
TRAY_FAILED = "[tray] start-up failed:"
TRAY_ALREADY = "another tray instance is running"


def tray_python() -> Path:
    """Windowless interpreter of the project environment (pythonw on Windows), so no console window appears."""
    venv = REPO / ".venv"
    if IS_WINDOWS:
        return venv / "Scripts" / "pythonw.exe"
    return venv / "bin" / "python"


def _startup_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _menu_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def menu_shortcut() -> Path:
    """Start menu entry that starts the tray, or opens its window when it is already running."""
    return _menu_dir() / SHORTCUT_NAME


def ensure_menu_shortcut() -> Path | None:
    """Create the Start menu entry if it is missing (Windows only). Returns its path, or None elsewhere."""
    if not IS_WINDOWS:
        return None
    lnk = menu_shortcut()
    if not lnk.exists():
        _make_shortcut(lnk, show=True)
    return lnk


def _make_shortcut(path: Path, show: bool = False) -> None:
    """Windows .lnk that runs the tray with pythonw from the repository folder. `show` opens its window on launch."""
    ps = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK_PATH); "
        "$s.TargetPath = $env:LNK_TARGET; $s.Arguments = $env:LNK_ARGS; $s.WorkingDirectory = $env:LNK_DIR; "
        "$s.Description = 'Agent Stack tray (personal-agent-stack)'; $s.WindowStyle = 7; $s.Save()"
    )
    args = f'"{TRAY_SCRIPT}"' + (" --show" if show else "")
    env = {**os.environ, "LNK_PATH": str(path), "LNK_TARGET": str(tray_python()), "LNK_ARGS": args, "LNK_DIR": str(REPO)}
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0)


def _autostart_file() -> Path:
    if IS_WINDOWS:
        return _startup_dir() / SHORTCUT_NAME
    return Path.home() / ".config" / "autostart" / "agent-stack.desktop"


def is_installed() -> bool:
    return _autostart_file().exists()


def install() -> Path:
    target = _autostart_file()
    if IS_WINDOWS:
        _make_shortcut(target)
    elif sys.platform.startswith("linux"):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "[Desktop Entry]\nType=Application\nName=Agent Stack\n"
            f"Exec={tray_python()} {TRAY_SCRIPT}\nPath={REPO}\nX-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )
    else:
        raise RuntimeError("start at login is implemented for Windows and Linux desktops only")
    return target


def remove() -> None:
    _autostart_file().unlink(missing_ok=True)


def request_show() -> None:
    """Ask the running tray to open its window (it watches for this file)."""
    SHOW_REQUEST.parent.mkdir(parents=True, exist_ok=True)
    SHOW_REQUEST.touch()


def take_show_request() -> bool:
    """True once per request_show(); the tray calls this from its UI loop."""
    try:
        SHOW_REQUEST.unlink()
        return True
    except OSError:
        return False


def launch_detached(show: bool = False) -> None:
    """Start the tray outside the current terminal/agent session (Windows: through Explorer, like the Start menu)."""
    python = tray_python()
    if not python.exists():
        raise FileNotFoundError(f"{python} not found; run `uv sync` first")
    if IS_WINDOWS:
        lnk = REPO / ".run" / SHORTCUT_NAME
        _make_shortcut(lnk, show=show)
        subprocess.run(["explorer.exe", str(lnk)], check=False)
    else:
        subprocess.Popen([str(python), str(TRAY_SCRIPT)] + (["--show"] if show else []), cwd=REPO, start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _log_since(log: Path, offset: int) -> str:
    try:
        with open(log, "rb") as f:
            f.seek(offset if offset <= os.fstat(f.fileno()).st_size else 0)  # a log cut shorter starts again
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


def _verdict(text: str, log: Path) -> tuple[str, str] | None:
    for line in text.splitlines():
        if TRAY_READY in line:
            pid = re.search(r"pid (\d+)", line)
            return "ready", f"running{f' (pid {pid.group(1)})' if pid else ''}"
        if TRAY_FAILED in line:
            return "failed", f"failed to start: {line.split(TRAY_FAILED, 1)[1].strip().rstrip('.')}. Details are in {log}"
        if TRAY_ALREADY in line:
            return "ready", "another tray was already running"
    return None


def wait_for_tray(log: Path, offset: int, timeout: float = 20.0, alive=None, poll: float = 0.25) -> tuple[str, str]:
    """Watch the tray log past `offset` until the new tray reports ready or failed. Returns (state, message): "ready",
    "failed", or "running" when it is alive but has said nothing by the timeout. `alive` returns the tray's pid."""
    alive = alive or running_pid
    deadline = time.monotonic() + timeout
    seen = None
    while True:
        verdict = _verdict(_log_since(log, offset), log)
        if verdict:
            return verdict
        pid = alive()
        if pid:
            seen = pid
        elif seen:  # it was up and is gone: read once more for its last words
            return _verdict(_log_since(log, offset), log) or ("failed", f"exited during start-up. Details are in {log}")
        if time.monotonic() >= deadline:
            if pid:
                return "running", f"started (pid {pid}) but has not reported ready after {timeout:.0f} s; if no icon appears, see {log}"
            return "failed", f"did not start within {timeout:.0f} s. Details are in {log}"
        time.sleep(poll)


def launch_and_wait(timeout: float = 20.0, show: bool = False) -> tuple[str, str]:
    """Start the tray detached, then confirm from its log that it came up, or say why it did not."""
    offset = TRAY_LOG.stat().st_size if TRAY_LOG.exists() else 0
    launch_detached(show=show)
    return wait_for_tray(TRAY_LOG, offset, timeout)


def running_pid() -> int | None:
    pid, started = services._read_pidfile(PIDFILE)
    if pid and started and services._proc_info(pid)[1] == started:
        return pid
    return None


def claim_single_instance() -> bool:
    """Record this process as the tray; False when another live tray already holds the pid file."""
    if running_pid():
        return False
    exe, started = services._proc_info(os.getpid())
    PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    services._write_pidfile(PIDFILE, os.getpid(), exe or sys.executable, started)
    return True


def report() -> None:
    pid = running_pid()
    info(f"tray: {'running (pid ' + str(pid) + ')' if pid else 'not running'}; start at login: {'on' if is_installed() else 'off'} ({_autostart_file()})")


def stop_tray() -> None:
    pid = running_pid()
    if not pid:
        info("tray: not running")
        return
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        os.kill(pid, 15)
    PIDFILE.unlink(missing_ok=True)
    info(f"tray: stopped pid {pid} (services keep running; `stack.py down` stops them)")
