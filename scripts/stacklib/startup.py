"""Tray app launch helpers: detached launch, start-at-login entry, single instance."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import IS_WINDOWS, REPO, info
from . import services

TRAY_SCRIPT = REPO / "scripts" / "tray.py"
SHORTCUT_NAME = "Agent Stack.lnk"
PIDFILE = REPO / ".run" / "pids" / "tray.pid"


def tray_python() -> Path:
    """Windowless interpreter of the project environment (pythonw on Windows), so no console window appears."""
    venv = REPO / ".venv"
    if IS_WINDOWS:
        return venv / "Scripts" / "pythonw.exe"
    return venv / "bin" / "python"


def _startup_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _make_shortcut(path: Path) -> None:
    """Windows .lnk that runs the tray with pythonw from the repository folder."""
    ps = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK_PATH); "
        "$s.TargetPath = $env:LNK_TARGET; $s.Arguments = $env:LNK_ARGS; $s.WorkingDirectory = $env:LNK_DIR; "
        "$s.Description = 'Agent Stack tray (personal-agent-stack)'; $s.WindowStyle = 7; $s.Save()"
    )
    env = {**os.environ, "LNK_PATH": str(path), "LNK_TARGET": str(tray_python()), "LNK_ARGS": f'"{TRAY_SCRIPT}"', "LNK_DIR": str(REPO)}
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


def launch_detached() -> None:
    """Start the tray outside the current terminal/agent session (Windows: through Explorer, like the Start menu)."""
    python = tray_python()
    if not python.exists():
        raise FileNotFoundError(f"{python} not found; run `uv sync` first")
    if IS_WINDOWS:
        lnk = REPO / ".run" / SHORTCUT_NAME
        _make_shortcut(lnk)
        subprocess.run(["explorer.exe", str(lnk)], check=False)
    else:
        subprocess.Popen([str(python), str(TRAY_SCRIPT)], cwd=REPO, start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
