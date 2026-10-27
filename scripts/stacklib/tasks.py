"""Supervision for `edge` mode (Plan B, B2b): one Task Scheduler task per native service, or systemd units on Linux.

Each task runs `stack.py run <svc>`, a small foreground supervisor that starts the service with the same command,
environment and log file as `stack.py up`, restarts it with backoff when it exits, and holds it in a kill-on-close job
object so ending the task (or the supervisor dying) also ends the service and its children. No pid files: the task is
the record of what runs.

Task Scheduler's "restart on failure" does not fire when a running task's process exits non-zero (tested 2026-10-26:
no restart within 2.5 minutes of killing the supervisor), so every task also has a repeating time trigger. While the
supervisor runs, those starts are ignored (IgnoreNew); after it dies, the next one starts it again. `tasks stop`
therefore disables the task as well as ending it, and `tasks start` enables it again.

Triggers: `startup` (before sign-in; S4U principal, needs an elevated shell to register, no stored password) or
`logon` (at the owner's sign-in; registers without elevation).
"""
from __future__ import annotations

import csv
import io
import os
import subprocess
import sys
import time
from pathlib import Path
from xml.sax.saxutils import escape

from . import IS_WINDOWS, REPO, info, warn
from . import services

TASK_FOLDER = "\\AgentStack\\"
STACK_PY = REPO / "scripts" / "stack.py"
SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"
WATCHDOG = "PT2M"  # how often Task Scheduler checks that the supervisor still runs
BACKOFF = [5, 10, 20, 40, 60]  # seconds between restarts of a failing service
HEALTHY_RUN = 300  # a run this long resets the backoff


def task_name(svc: str) -> str:
    return f"{TASK_FOLDER}{svc}"


def _venv_python(windowless: bool) -> Path:
    venv = REPO / ".venv"
    if IS_WINDOWS:
        return venv / "Scripts" / ("pythonw.exe" if windowless else "python.exe")
    return venv / "bin" / "python"


# ---------------------------------------------------------------- supervisor (`stack.py run <svc>`)


def _kill_on_close_job() -> object | None:
    """Put this process in a new job that kills every member when its last handle closes, so the service and its
    children cannot outlive the supervisor. Children inherit the job, so there is no window between spawn and assign."""
    if not IS_WINDOWS:
        return None
    import ctypes
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("r", "w", "o", "rb", "wb", "ob")]

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class EXTENDED(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    k32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return None
    limits = EXTENDED()
    limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):  # 9 = extended limits
        return None
    if not k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()):
        return None
    return job  # keep the handle for the life of the process


def _log_line(log, msg: str) -> None:
    log.write(f"[supervisor {time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n".encode("utf-8"))
    log.flush()


def run(profile: dict, svc: str) -> int:
    """Run one service in the foreground and restart it when it exits. Returns only on a clean exit (code 0)."""
    cmds = services.commands(profile)
    if svc not in cmds:
        warn(f"{svc}: not configured on this profile")
        return 2
    c = cmds[svc]
    job = _kill_on_close_job()
    log = open(services.run_dir(profile) / "logs" / f"{svc}.log", "ab")
    if IS_WINDOWS and not job:
        _log_line(log, "could not create a kill-on-close job; the service may outlive this supervisor")
    attempt = 0
    while True:
        if services._http_ok(services.health_url(profile, svc)):
            # Another copy (the tray or `stack.py up`) holds the port: wait instead of starting a second one.
            _log_line(log, "something already answers on the service port; checking again in 30 s")
            while services._http_ok(services.health_url(profile, svc)):
                time.sleep(30)
        _log_line(log, f"starting {svc}: {c['cmd'][0]}")
        began = time.time()
        try:
            proc = subprocess.Popen(c["cmd"], cwd=c["cwd"], env=c["env"], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            code = proc.wait()
        except OSError as e:  # missing executable, or Smart App Control refusing it (WinError 4551)
            _log_line(log, f"could not start {c['cmd'][0]}: {e}")
            code = -1
        if code == 0:
            _log_line(log, f"{svc} exited cleanly")
            return 0
        attempt = 0 if time.time() - began >= HEALTHY_RUN else attempt + 1
        delay = BACKOFF[min(max(attempt - 1, 0), len(BACKOFF) - 1)]
        _log_line(log, f"{svc} exited with code {code} after {time.time() - began:.0f} s; restarting in {delay} s")
        time.sleep(delay)


# ---------------------------------------------------------------- Windows Task Scheduler


def _current_user() -> tuple[str, str]:
    """(DOMAIN\\user, SID) of the signed-in user."""
    out = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, check=True).stdout
    name, sid = next(csv.reader(io.StringIO(out.strip())))
    return name, sid


def task_xml(svc: str, trigger: str) -> str:
    user, sid = _current_user()
    if trigger == "startup":
        trig = "<BootTrigger><Enabled>true</Enabled><Delay>PT30S</Delay></BootTrigger>"
        logon_type = "S4U"  # runs whether or not the user is signed in; no stored password; local resources only
    else:
        trig = f"<LogonTrigger><Enabled>true</Enabled><UserId>{escape(user)}</UserId><Delay>PT15S</Delay></LogonTrigger>"
        logon_type = "InteractiveToken"
    # Watchdog: repeats forever from a fixed past date; a start while the task runs is ignored (IgnoreNew).
    trig += (f"<TimeTrigger><Enabled>true</Enabled><StartBoundary>2026-01-01T00:00:00</StartBoundary>"
             f"<Repetition><Interval>{WATCHDOG}</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition></TimeTrigger>")
    python = _venv_python(windowless=True)  # no console window in the signed-in session
    args = f'"{STACK_PY}" run {svc}'
    # Priority 5 is normal; Task Scheduler's default (7) lowers CPU and I/O priority.
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>personal-agent-stack</Author>
    <Description>Agent stack service '{escape(svc)}' (GENERATED by `stack.py tasks install`; log: .run/logs/{escape(svc)}.log)</Description>
  </RegistrationInfo>
  <Triggers>{trig}</Triggers>
  <Principals>
    <Principal id="Author"><UserId>{escape(sid)}</UserId><LogonType>{logon_type}</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>5</Priority>
    <RestartOnFailure><Interval>PT1M</Interval><Count>999</Count></RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec><Command>{escape(str(python))}</Command><Arguments>{escape(args)}</Arguments><WorkingDirectory>{escape(str(REPO))}</WorkingDirectory></Exec>
  </Actions>
</Task>
"""


def _schtasks(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks", *args], capture_output=True, text=True)


def registered() -> set[str]:
    """Services that have a task in the AgentStack folder (empty off Windows or when none exist)."""
    if not IS_WINDOWS:
        return {p.stem.removeprefix("agent-stack-") for p in SYSTEMD_DIR.glob("agent-stack-*.service")} if SYSTEMD_DIR.exists() else set()
    r = _schtasks("/Query", "/FO", "CSV", "/NH")
    names = set()
    for row in csv.reader(io.StringIO(r.stdout)):
        if row and row[0].lower().startswith(TASK_FOLDER.lower()):
            names.add(row[0][len(TASK_FOLDER):])
    return names


def task_dir(profile: dict) -> Path:
    d = services.run_dir(profile) / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _service_list(profile: dict, names: list[str] | None) -> list[str]:
    cmds = services.commands(profile)
    return names or [s for s in services.SERVICE_ORDER if s in cmds]


def install(profile: dict, names: list[str] | None, trigger: str, write_only: bool = False) -> bool:
    if not IS_WINDOWS:
        return _install_systemd(profile, names, write_only)
    ok = True
    for svc in _service_list(profile, names):
        path = task_dir(profile) / f"{svc}.xml"
        path.write_text(task_xml(svc, trigger), encoding="utf-16")
        if write_only:
            info(f"{svc}: wrote {path}")
            continue
        r = _schtasks("/Create", "/TN", task_name(svc), "/XML", str(path), "/F")
        if r.returncode == 0:
            info(f"{svc}: task {task_name(svc)} registered ({trigger})")
        else:
            ok = False
            warn(f"{svc}: schtasks refused: {(r.stderr or r.stdout).strip()}")
    if not ok and trigger == "startup":
        warn("'startup' tasks run before sign-in (S4U) and need an elevated shell to register. In an admin terminal: "
             f"uv run scripts/stack.py tasks install --trigger startup")
    return ok


def remove(profile: dict, names: list[str] | None) -> None:
    if not IS_WINDOWS:
        for svc in names or sorted(registered()):
            subprocess.run(["systemctl", "--user", "disable", "--now", f"agent-stack-{svc}.service"], check=False)
            (SYSTEMD_DIR / f"agent-stack-{svc}.service").unlink(missing_ok=True)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        return
    for svc in names or sorted(registered()):
        r = _schtasks("/Delete", "/TN", task_name(svc), "/F")
        info(f"{svc}: {'task removed' if r.returncode == 0 else 'not removed: ' + (r.stderr or r.stdout).strip()}")


def start(profile: dict, names: list[str] | None) -> None:
    for svc in names or [s for s in services.SERVICE_ORDER if s in registered()]:
        if IS_WINDOWS:
            _schtasks("/Change", "/TN", task_name(svc), "/ENABLE")
            r = _schtasks("/Run", "/TN", task_name(svc))
        else:
            r = subprocess.run(["systemctl", "--user", "start", f"agent-stack-{svc}.service"], capture_output=True, text=True)
        info(f"{svc}: {'started' if r.returncode == 0 else 'not started: ' + (r.stderr or r.stdout).strip()}")


def stop(profile: dict, names: list[str] | None) -> None:
    for svc in names or [s for s in reversed(services.SERVICE_ORDER) if s in registered()]:
        if IS_WINDOWS:
            # Disable first, or the watchdog trigger starts it again within minutes; `tasks start` re-enables it.
            r = _schtasks("/Change", "/TN", task_name(svc), "/DISABLE")
            _schtasks("/End", "/TN", task_name(svc))
        else:
            r = subprocess.run(["systemctl", "--user", "stop", f"agent-stack-{svc}.service"], capture_output=True, text=True)
        info(f"{svc}: {'stopped (task disabled until `tasks start`)' if r.returncode == 0 else 'not stopped: ' + (r.stderr or r.stdout).strip()}")


def status(profile: dict) -> list[dict]:
    rows = []
    for svc in [s for s in services.SERVICE_ORDER if s in registered()]:
        row = {"service": svc, "state": "?", "last_result": "?", "trigger": "?", "healthy": services._http_ok(services.health_url(profile, svc))}
        if IS_WINDOWS:
            r = _schtasks("/Query", "/TN", task_name(svc), "/FO", "CSV", "/V")
            parsed = list(csv.DictReader(io.StringIO(r.stdout)))
            if parsed:
                row.update(state=parsed[0].get("Status", "?"), last_result=parsed[0].get("Last Result", "?"),
                           trigger=parsed[0].get("Schedule Type", "?").strip())
        else:
            r = subprocess.run(["systemctl", "--user", "is-active", f"agent-stack-{svc}.service"], capture_output=True, text=True)
            row.update(state=r.stdout.strip(), last_result="-", trigger="systemd --user")
        rows.append(row)
    return rows


# ---------------------------------------------------------------- Linux: systemd user units (generated, untested)


def unit_text(svc: str) -> str:
    return f"""# GENERATED by `stack.py tasks install`. Untested on a Linux host so far.
[Unit]
Description=Agent stack service {svc}
After=network-online.target

[Service]
Type=simple
WorkingDirectory={REPO}
ExecStart={_venv_python(windowless=False)} {STACK_PY} run {svc}
Restart=on-failure
RestartSec=10
KillMode=control-group

[Install]
WantedBy=default.target
"""


def _install_systemd(profile: dict, names: list[str] | None, write_only: bool) -> bool:
    SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)
    for svc in _service_list(profile, names):
        path = SYSTEMD_DIR / f"agent-stack-{svc}.service"
        path.write_text(unit_text(svc), encoding="utf-8")
        info(f"{svc}: wrote {path}")
    if write_only:
        return True
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    for svc in _service_list(profile, names):
        subprocess.run(["systemctl", "--user", "enable", f"agent-stack-{svc}.service"], check=False)
    info("enabled; units start at boot only with lingering on: loginctl enable-linger $USER")
    return True


def main_run(profile: dict, svc: str) -> int:
    # Under pythonw there is no console; keep stray prints from failing.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    return run(profile, svc)
