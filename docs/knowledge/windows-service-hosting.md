# Keeping background services alive on a Windows desktop

Related: [Stopping AI agents from reading personal files](agent-file-isolation.md).

## 1. What this is and why the project needs it

The stack is a handful of programs that must keep running without anyone watching them: the model gateway, the
orchestrator, Open WebUI and (until it was blocked) Phoenix. They run on an ordinary Windows 11 desktop, not on a
server. That desktop has a person at the keyboard who closes windows, signs out, reboots and runs security features.
Each of those events can end a program that was started the wrong way. This note explains how Windows starts, groups
and stops programs, so that you can see why `scripts/stacklib/services.py` is written the way it is and why the
lessons in `memory/lessons.md` came out as they did.

## 2. The ideas, built up from zero

### 2.1 Processes and ids

A program on disk is just a file. When Windows runs it, Windows creates a **process**: a running copy with its own
memory, its own open files and a number called the **process id** (pid). Picture a building where each running
program gets a room and a room number. You talk to a room by number: "stop room 4120".

Room numbers get reused. When a process ends, its pid goes back into a pool, and a later process can receive the
same number. If you wrote down "4120" yesterday and the original process is gone, 4120 may now be a browser. The
analogy stops working in one way: a real room number never changes hands this fast. Windows hands a freed pid to a
new process, sometimes soon after.

So a pid alone is not an identity. The fix is to write down a second fact that cannot repeat for the same room: the
moment the process was created, called its **start time**. A pid plus a start time names exactly one process, ever.
The project stores both (section 5). On Windows the start time comes from the call `GetProcessTimes`, on Linux from
field 22 of `/proc/<pid>/stat`, elsewhere from `ps -o lstart`.

### 2.2 Parents, children and trees

A process starts other processes. The starter is the **parent**; the new one is the **child**. Children can have
children, which makes a **process tree**. Here is the tree for one service on Windows:

```
tray app (pythonw.exe)                      <- started through Explorer
 └─ python.exe  (venv launcher, pid 6100)   <- the pid we record
     └─ python.exe  (real interpreter)      <- runs LiteLLM, listens on port 4000
         └─ worker processes (maybe)
```

The pid numbers and the worker line are illustrative. Killing the top process does not always kill the rest. On
Windows, children keep running if the parent dies; they become orphans. So stopping a service means stopping the whole
tree (`taskkill /T`) and, as a safety net, whatever still listens on the service's port. `services.stop()` does both.

### 2.3 Launchers: why one service is two or three processes

Many Windows tools start through a small **launcher** program. A virtual environment's `Scripts\python.exe` is such a
launcher: it finds the real interpreter and starts it as a child. `uv.exe` does the same when you run `uv run`. The
pid you get from "start this" is the launcher's pid, not the server's. That is why the project records the launcher
and kills the tree.

`uv tool install` also writes one small `.exe` per command into `~/.local/bin` (for example `litellm.exe`). Each of
those embeds its own script, so every one is a different file. Remember this for section 2.6.

The project avoids those per-tool files. It runs `<env>\Scripts\python.exe -P -c "<call the console script's entry
point>"`. A console script is a command name (`litellm`) that maps to a function in a package; the mapping lives in the
package's `entry_points.txt`, and `services._console_script_target` reads it. The `-P` flag (Python 3.11 and later)
keeps the current folder off the import path, so a folder in the repository cannot hide a real library.

### 2.4 Consoles and windows

A Windows program that prints text normally has a **console**, a text window. A process can start in three ways with
respect to consoles: share its parent's console, get a new visible one, or run with none. Two creation flags matter:

- `DETACHED_PROCESS`: the new process has no console at all.
- `CREATE_NO_WINDOW`: the new process has a console, but Windows does not show it.

The difference bites with launchers. A launcher with no console starts its child, and the child, needing a console,
gets a new visible one. The service now lives in a window. On 2026-10-25 the services died when their "CMD windows"
were closed. With `CREATE_NO_WINDOW`, the child inherits the parent's hidden console; nothing shows and nothing can
be closed. The project uses `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP` (the second flag is the new-process-group
flag; the code does not say why it is there beyond that).

### 2.5 Job objects: groups that die together

A **job object** is a Windows group of processes. A job can carry limits. One limit, **kill on close**, says: when the
last handle to the job closes, end every process in it. Terminals, remote sessions and agent tool shells may use this (our inference)
so that closing the session cleans up everything it started. Children inherit their parent's job automatically.

That is the likely reason services started from a Claude Code tool shell died with the session: the lessons record
that they "die when that session ends (job object)". They were in the shell's job, and the job closed.

A process can ask to leave its parent's job with the creation flag `CREATE_BREAKAWAY_FROM_JOB`. Windows allows this
only if the job permits breakaway. If it does not, the start fails with a permission error. `services.start()` first
asks for breakaway, and on `PermissionError` retries without it and warns. Even when the flag was used, the project saw
services stop with one session and survive the next, so the flag is a hope, not a guarantee.

The project also uses job objects on purpose. The scheduled-task supervisor puts itself into a new kill-on-close job
before it starts the service. If the supervisor dies, Windows ends the service and its children too. Because children
inherit the job, there is no gap between "spawn" and "assign" in which a child could escape. This is the same
mechanism as the trap above, used to make cleanup reliable instead of surprising.

### 2.6 Smart App Control and code integrity

**Smart App Control** (SAC) is a Windows 11 feature that decides whether a file may run. It judges a file by its
**reputation** and signature. A file that is unsigned and not known to be common may be blocked. The inner component
is **code integrity**; each block writes an event to the CodeIntegrity log (events 3033 and 3077 in this project's
records). The program that tried to start sees an error, `WinError 4551`. The exact reputation mechanism is not
described in the repository.

Two facts make this awkward for developer tools:

1. SAC judges **file by file**. A new unsigned `.exe` has no track record, so it may be blocked even if a sibling
   tool ran an hour ago. Each uv launcher is a unique file, so `phoenix.exe` was blocked (2026-10-25 19:34) while
   `litellm.exe` still ran.
2. SAC also judges **compiled Python modules** (`.pyd` files, which are DLLs). Phoenix's environment ran one day
   and the next day SAC blocked `pyarrow`'s `_parquet`, a SQLAlchemy module and a pandas module.

The standard `python.exe` in a venv is the same file in every environment, so it has not been blocked. That is the
reason for starting tools through it. It is a workaround, not a fix: if SAC ever blocks it too, the remaining options
are to turn SAC off (the owner's security decision) or to run tools under the signed `uv`.

### 2.7 Running something outside any session

A service must not belong to a window, a terminal or an agent session. Windows offers four ways, from lightest to
heaviest.

**Startup-folder shortcut.** A `.lnk` file in the user's Startup folder runs when that user signs in. Cheap and
visible, but nothing runs before sign-in and nothing restarts a crash.

**A tray app launched through Explorer.** If the shortcut is opened by `explorer.exe` (as the Start menu does), the
new program's parent is Explorer, not your terminal, so it is in no terminal's job. `stack.py tray` does this
(`startup.launch_detached`). The tray then starts the services as its own children. The tray survives sessions; the
services live as long as the tray. It still needs a signed-in user.

**Task Scheduler.** Windows' built-in scheduler runs a task on a **trigger**. The two that matter:

- *Logon trigger*: runs when the owner signs in. Registers without administrator rights.
- *Startup (boot) trigger*: runs when Windows boots, before anyone signs in. The task runs under a **principal**; the
  project uses **S4U** ("service for user"), which runs as the owner without a stored password (the code comment
  adds: local resources only). Registering it needs an elevated shell. It matters for the `edge` access mode, where
  invited users reach the PC while nobody may be signed in.

Task Scheduler has a "restart on failure" setting. It did not fire when the running task's process was killed or exited non-zero (tested
2026-10-26: no restart within 2.5 minutes). The workaround is a second trigger: a **repeating time trigger** every
2 minutes with `MultipleInstancesPolicy = IgnoreNew`. While the supervisor runs, the repeated start is ignored; once it
dies, the next repeat starts it. That is a **watchdog**. The cost: a watchdog also revives a service you stopped on
purpose, so a deliberate stop must **disable** the task first (`tasks stop` does, and `tasks start` re-enables it).

**Windows services.** The service control manager starts programs at boot, restarts them on failure and runs them
without a desktop. A program must speak the service protocol or be wrapped. Keycloak ships its own wrapper
(`kc.bat tools windows-service install`, Apache Commons Daemon). The project has not installed it; it needs an
elevated shell.

### 2.8 Health checks, not handles

After starting a service you hold a handle to the process. Do not trust it. The process you started may be a launcher
that exits while the real server keeps running, or the server may be alive but stuck. Ask the service instead: call its
**health URL** (an HTTP address that answers when the server is ready). `services.status()` reports "running" when
the health URL answers, "starting" when the recorded process is alive but silent, and "stopped" otherwise.

### 2.9 Ports and listeners

A server **listens** on a **port** (a number, such as 4000) on an address. Only one process can listen on a given
address and port at a time. `127.0.0.1` means "this computer only", so other machines cannot connect. The project
checks the health URL before starting ("something already answers on its port") and, on stop, looks up listeners with
`netstat -ano` (Linux: `lsof`) to kill anything still holding the port. It does this only when the port answers that
service's health check, so it never kills an unrelated program.

### 2.10 Other systems, briefly

On Linux, **systemd** is the supervisor. A unit file says how to start the program, `Restart=on-failure` restarts
it, and `KillMode=control-group` ends the whole process group, much like a kill-on-close job. User units start at boot
only if "lingering" is on (`loginctl enable-linger`). The project generates systemd user units but has not run them
on a Linux host. macOS: launchd is the equivalent; the project has no launchd code.

### 2.11 Declaring what to install: winget configuration

`winget configure` reads a **WinGet Configuration file** that lists packages and settings, and applies them. The
project keeps one in `winget/configuration.winget` (generated; `configuration.edge.winget` adds OpenJDK and Caddy) so
a clean PC can be rebuilt in one step. winget first needs `winget configure --enable`, run once per machine.
Installed binaries still face Smart App Control.

## 3. Rules of thumb and typical numbers

| Rule | Source |
|---|---|
| Identify a process by pid and start time, never by pid alone or by program name alone. | `memory/lessons.md` 2026-10-25 |
| A shared launcher makes a program-name check useless: six long-lived `uv.exe` MCP servers run on this machine. | `memory/state.md` |
| Start services with `CREATE_NO_WINDOW`, not `DETACHED_PROCESS`; stop by tree and by port; read status from the health check. | lessons 2026-10-25 |
| Do not depend on a launching shell's job; use the tray, a scheduled task or a service. | lessons 2026-10-25 |
| Treat Task Scheduler "restart on failure" as unreliable; add a 2-minute repeating trigger with `IgnoreNew`. | lessons 2026-10-26, V10 |
| Disable a watchdog-supervised task when you stop it on purpose. | lessons 2026-10-26 |
| Put a supervisor in a kill-on-close job before spawning children. | lessons 2026-10-26 |
| Backoff between restarts of a failing service: 5, 10, 20, 40, 60 s; a run of 300 s resets it. | `scripts/stacklib/tasks.py` |
| Boot trigger delay 30 s, logon trigger delay 15 s, watchdog every 2 min. | `scripts/stacklib/tasks.py` |
| Cold load of the 9B model from the USB drive took 2 min 10 s; `wait_healthy` defaults to 120 s; `stack.py up --wait` defaults to 150 s. | `memory/state.md`, `services.py`, `stack.py` |
| Keycloak `start-dev`: 13.8 s to start, 411 MB idle, 514-517 MB after 300 logins. | SHARED-COMPONENTS V7 |

## 4. Common misconceptions and edge cases

**"The pid in my file is the server."** Often it is a launcher. The real server is a child.

**"If the pid exists, my service is up."** The pid may belong to another program, or to your service while it is
hung. Check the start time and the health URL.

**"Closing a window only closes the window."** If the window held the console that a service shares, closing it ends
the service (section 2.4).

**"`CREATE_BREAKAWAY_FROM_JOB` makes a service permanent."** It works only when the job allows breakaway, and the
project saw mixed results. It is not a substitute for Task Scheduler or the tray.

**"A tool that ran yesterday will run today."** Smart App Control judged `.pyd` modules inside a tool environment
that had run the day before. An environment can break without any change you made.

**"Restart on failure restarts a killed task."** Not in the tested case (section 2.7).

**"A Startup shortcut starts services at boot."** It starts them at sign-in. Boot-time start needs a startup trigger
(elevated registration) or a Windows service.

**"The tray is the service manager."** In `owner` mode it is. In `edge` mode, tasks own the services and the tray
only shows status. `up`, `down` and the tray skip any service that has a scheduled task.

**Edge case: orphaned children.** If a launcher dies, its child can keep the port. `stop` finds it by port.

**Edge case: stale pid file.** After a reboot the pid may belong to something new. The start-time check catches this.
A pid file written before start times were recorded falls back to matching the launcher's name.

**Edge case: `pythonw.exe`.** It has no console, so `print` can fail. The task entry point replaces a missing
`sys.stdout` with a null device (`main_run`).

## 5. How the project uses it

**Commands.**

```
uv run scripts/stack.py up | down | status       # start, stop, show the native services
uv run scripts/stack.py tray                     # tray app launched through Explorer; owns the services
uv run scripts/stack.py tray --status | --remove-startup
uv run scripts/stack.py tasks install [--trigger startup|logon] | start | stop | status | remove | xml
# install defaults to --trigger startup, which needs an elevated shell; logon does not
uv run scripts/stack.py run <svc>                # the foreground supervisor a task runs
```

**Files.**

- `scripts/stacklib/services.py`: `tool_command` (start a uv tool through its environment's Python),
  `start`/`stop`/`status`, pid files, `_proc_info` (executable and start time), `port_pids` and `_kill_tree`.
- `scripts/stacklib/startup.py`: `launch_detached` (Explorer launch), the Startup-folder shortcut `Agent Stack.lnk`,
  and the tray's single-instance pid file.
- `scripts/stacklib/tasks.py`: Task Scheduler XML (folder `\AgentStack\`), the supervisor with its kill-on-close
  job, systemd unit text.
- `scripts/tray.py`: the tray and its status window.

**Pid file format.** `.run/pids/<service>.pid`, three lines: the pid, the executable path, the process start time
(Windows creation FILETIME, Linux clock ticks since boot, or the `ps` string). A pid counts as the service only
while a live process has that pid and that start time. `down` leaves a mismatched process alone and warns.

**Design choices.**

- Native processes, no Docker, because WSL2 and Docker Desktop would reserve RAM the models need
  ([decision](../decisions/2026-10-24-native-services-no-docker.md)).
- Two modes ([PLAN-B](../plans/PLAN-B-LOCAL-LED.md), section 1.1): `owner` (the owner on this machine; tray and
  Startup shortcut) and `edge` (invited users anywhere; Task Scheduler startup tasks, so services run before sign-in).
- Task-run services keep no pid files: the task is the record. The supervisor restarts with backoff and waits when
  something already answers on the service port.
- Services start with `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`, with a retry
  without breakaway.
- A failed start of one service warns and continues, so one Smart App Control block does not stop the batch.

More: [tray app plan](../design/plans/2026-10-25-tray-app.md), [DECISIONS.md](../design/DECISIONS.md),
[SHARED-COMPONENTS.md](../plans/SHARED-COMPONENTS.md) (V7, V9, V10), [INSTALL.md](../plans/INSTALL.md) (step 14),
[troubleshooting](../manuals/troubleshooting.md).

## 6. What we found

- **2026-10-25.** Processes launched from an agent tool shell died when the session ended. Launching with
  `CREATE_BREAKAWAY_FROM_JOB` helped once and failed once; the lessons were corrected twice the same day.
- **2026-10-25.** `phoenix.exe` was blocked by Smart App Control (WinError 4551) while `litellm.exe` ran. The project
  switched to the tool environments' `python.exe`; no CodeIntegrity events since.
- **2026-10-25.** Closing the console windows killed services started with `DETACHED_PROCESS`. `CREATE_NO_WINDOW`
  fixed it. Pid reuse led to start-time matching; the check was verified by pointing a pid file at a live `uv.exe`.
- **2026-10-25.** A tray app launched through Explorer kept services alive across Claude Code sessions. Icon updates
  from two threads at once failed with WinError 1402, so they are serialised.
- **2026-10-26.** Task Scheduler did not restart a killed supervisor. A repeating 2-minute trigger restarted Phoenix
  1 min 43 s after a kill (V10). Registering a startup (S4U) task from a normal shell failed with "Access is denied";
  it needs an elevated shell and has not been run.
- **2026-10-26.** Smart App Control blocked `.pyd` modules (pyarrow, sqlalchemy, pandas) in the Phoenix environment;
  Phoenix did not start here and the plans remove it (V9). It allowed `java.exe`, Keycloak and `caddy.exe`.
- **2026-10-26.** A kill-on-close job in the supervisor ends the service tree with it.
- **2026-10-26.** With the tray on `main`, all five services were up; start at login has been on since 2026-10-25.

## 7. Open questions

- Do the tray and its services come up on their own after the next reboot? (state.md open item 2)
- Does a startup (S4U) task run correctly before sign-in? Not tested; needs an elevated shell.
- Will Smart App Control ever block the environments' `python.exe`? The fallback is the owner's decision.
- Does the systemd path work on a real Linux host? Written, not run.
- Should the stack move to real Windows services? Not decided.
- `winget configure` has not been run end to end on a clean account (V9).
- Why did breakaway persistence vary between sessions? Cause not found.

## 8. Sources and further reading

No external Microsoft documentation URL is recorded in the repository, so none is listed. Source not recorded for the
general Windows facts in section 2 (job-object semantics, creation flags, S4U, how SAC rates files); they match the
project's observations and its code comments, but are not cited to outside documents.

| Title | Org, year | What it is good for |
|---|---|---|
| `memory/lessons.md` (2026-10-25 and 2026-10-26 entries) | this project, 2026 | The dated findings above |
| [SHARED-COMPONENTS.md](../plans/SHARED-COMPONENTS.md) V7, V9, V10 | this project, 2026 | Measured results for Keycloak, winget, Task Scheduler |
| [Tray app plan](../design/plans/2026-10-25-tray-app.md) | this project, 2026 | Why the tray exists |
| [Native services decision](../decisions/2026-10-24-native-services-no-docker.md) | this project, 2026 | Why not Docker |
| [PLAN-B-LOCAL-LED.md](../plans/PLAN-B-LOCAL-LED.md) | this project, 2026 | `owner` and `edge` modes, B2b |
| `scripts/stacklib/services.py`, `tasks.py`, `startup.py` | this project, 2026 | The code, with comments on each Windows trick |

## Changes

- 2026-11-01: first version.
