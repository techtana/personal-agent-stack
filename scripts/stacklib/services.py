"""Start/stop/status for the native services (LiteLLM, Phoenix, orchestrator MCP, Open WebUI)."""
from __future__ import annotations

import os
import re
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import IS_WINDOWS, LITELLM_DIR, REPO, TRACES_DIR, env_value, info, load_dotenv, warn, which

SERVICE_ORDER = ["phoenix", "litellm", "orchestrator", "open_webui"]

# Services that are uv tools: (uv tool environment, console script). They start through the environment's own
# Python, not the per-script launcher uv writes to ~/.local/bin. Smart App Control judges each executable by
# reputation: every launcher is a unique file (the script is embedded), so it can be blocked (phoenix.exe was,
# WinError 4551), while the environment's python.exe is the same standard venv launcher everywhere and runs.
TOOL_SCRIPTS = {
    "phoenix": ("arize-phoenix", "phoenix"),
    "litellm": ("litellm", "litellm"),
    "open_webui": ("open-webui", "open-webui"),
}
_uv_tool_dir_cache: list[Path | None] = []


def _uv_tool_dir() -> Path | None:
    """`uv tool dir`, cached for the life of the process."""
    if not _uv_tool_dir_cache:
        out = ""
        uv = which("uv")
        if uv:
            try:
                # uv writes UTF-8; decoding with the ANSI code page would break on a non-ASCII profile path.
                raw = subprocess.run([uv, "tool", "dir"], capture_output=True, timeout=30).stdout
                out = raw.decode("utf-8", "replace").strip()
            except (OSError, subprocess.TimeoutExpired):
                out = ""
        _uv_tool_dir_cache.append(Path(out) if out else None)
    return _uv_tool_dir_cache[0]


def _norm_dist(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


def _console_script_target(env_dir: Path, dist: str, script: str) -> str | None:
    """The 'module:attr' a console script runs, read from the tool environment's installed entry_points.txt.
    The tool's own distribution is searched first, so a dependency that ships a same-named script cannot win."""
    sites = [env_dir / "Lib" / "site-packages"] if IS_WINDOWS else sorted(env_dir.glob("lib/python*/site-packages"))
    for site in sites:
        eps = sorted(site.glob("*.dist-info/entry_points.txt"), key=lambda ep: (_norm_dist(ep.parent.name.split("-")[0]) != _norm_dist(dist), ep.name))
        for ep in eps:
            section = ""
            for raw in ep.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.strip()
                if not line or line[0] in "#;":
                    continue
                if line.startswith("["):
                    section = line
                elif section == "[console_scripts]" and "=" in line:
                    name, target = (part.strip() for part in line.split("=", 1))
                    if name == script:
                        return target.split()[0]  # drop any "[extra]" marker
    return None


def _env_python_version(env_dir: Path) -> tuple[int, int] | None:
    """(major, minor) of a virtual environment's interpreter, from its pyvenv.cfg."""
    try:
        for line in (env_dir / "pyvenv.cfg").read_text(encoding="utf-8", errors="replace").splitlines():
            key, _, value = line.partition("=")
            if key.strip() in ("version_info", "version"):
                major, minor = value.strip().split(".")[:2]
                return int(major), int(minor)
    except (OSError, ValueError):
        pass
    return None


def tool_command(svc: str) -> list[str]:
    """Argv prefix that runs a uv tool's console script through the tool environment's Python.

    `-P` keeps the working directory off sys.path, as the uv launchers do, so folders in the repository can never
    shadow a library; it exists from Python 3.11, so it is added only when the environment is known to be 3.11+.
    Falls back to the launcher on PATH when the environment or entry point cannot be found.
    """
    env_name, script = TOOL_SCRIPTS[svc]
    tool_dir = _uv_tool_dir()
    if tool_dir:
        env_dir = tool_dir / env_name
        python = env_dir / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
        target = _console_script_target(env_dir, env_name, script)
        if python.exists() and target and ":" in target:
            module, attr = target.split(":", 1)
            code = (
                f"import functools, importlib, sys; sys.argv[0] = {script!r}; "
                f"sys.exit(functools.reduce(getattr, {attr.split('.')!r}, importlib.import_module({module!r}))())"
            )
            version = _env_python_version(env_dir)
            flags = ["-P"] if version and version >= (3, 11) else []
            return [str(python), *flags, "-c", code]
    warn(f"{svc}: uv tool environment '{env_name}' not found; falling back to the '{script}' launcher on PATH")
    return [which(script) or script]


def run_dir(profile: dict) -> Path:
    d = Path(profile["data_dir"])
    (d / "pids").mkdir(parents=True, exist_ok=True)
    (d / "logs").mkdir(parents=True, exist_ok=True)
    return d


def _http_ok(url: str, headers: dict | None = None, timeout: float = 3.0) -> bool:
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except (urllib.error.URLError, OSError):
        return False


def health_url(profile: dict, svc: str) -> str:
    p = profile["ports"]
    return {
        "litellm": f"http://127.0.0.1:{p['litellm']}/health/liveliness",
        "phoenix": f"http://127.0.0.1:{p['phoenix']}/",
        "orchestrator": f"http://127.0.0.1:{p['orchestrator']}/healthz",
        "open_webui": f"http://127.0.0.1:{p['open_webui']}/health",
        "ollama": f"http://127.0.0.1:{p['ollama']}/api/version",
    }[svc]


def commands(profile: dict) -> dict[str, dict]:
    """Command line, cwd and env for each native service."""
    dotenv = load_dotenv()
    p = profile["ports"]
    d = run_dir(profile)
    master = env_value("LITELLM_MASTER_KEY", dotenv)
    base_env = dict(os.environ)
    base_env.update({k: v for k, v in dotenv.items() if k not in base_env})
    base_env["PYTHONIOENCODING"] = "utf-8"
    out: dict[str, dict] = {}
    if profile["observability"].get("phoenix"):
        out["phoenix"] = {
            "cmd": [*tool_command("phoenix"), "serve"],
            "cwd": str(REPO),
            "env": {**base_env, "PHOENIX_PORT": str(p["phoenix"]), "PHOENIX_GRPC_PORT": str(p["phoenix_grpc"]), "PHOENIX_HOST": "127.0.0.1", "PHOENIX_WORKING_DIR": str(d / "phoenix")},
        }
    litellm_env = {**base_env, "LITELLM_MASTER_KEY": master, "TRACES_DIR": str(TRACES_DIR / "litellm"), "LITELLM_LOG": "INFO"}
    if profile["observability"].get("phoenix"):
        litellm_env.update({"OTEL_EXPORTER": "otlp_http", "OTEL_ENDPOINT": f"http://127.0.0.1:{p['phoenix']}/v1/traces", "OTEL_SERVICE_NAME": "litellm"})
    out["litellm"] = {
        "cmd": [*tool_command("litellm"), "--config", str(LITELLM_DIR / "config.yaml"), "--host", "127.0.0.1", "--port", str(p["litellm"])],
        "cwd": str(LITELLM_DIR),
        "env": litellm_env,
    }
    out["orchestrator"] = {
        "cmd": [which("uv") or "uv", "run", "--quiet", "python", "-m", "orchestrator.server"],
        "cwd": str(REPO),
        "env": {
            **base_env,
            "ORCHESTRATOR_BEARER": env_value("ORCHESTRATOR_BEARER", dotenv),
            "ORCHESTRATOR_PORT": str(p["orchestrator"]),
            "LITELLM_BASE_URL": f"http://127.0.0.1:{p['litellm']}",
            "LITELLM_MASTER_KEY": master,
            "AGENT_STACK_REPO": str(REPO),
        },
    }
    if profile["services"].get("open_webui") == "native":
        out["open_webui"] = {
            "cmd": [*tool_command("open_webui"), "serve", "--host", "127.0.0.1", "--port", str(p["open_webui"])],
            "cwd": str(REPO),
            "env": {
                **base_env,
                "DATA_DIR": str(d / "open-webui"),
                "WEBUI_SECRET_KEY": env_value("WEBUI_SECRET_KEY", dotenv),
                "WEBUI_URL": f"http://127.0.0.1:{p['open_webui']}",
                "ENABLE_OPENAI_API": "true",
                "OPENAI_API_BASE_URL": f"http://127.0.0.1:{p['litellm']}/v1",
                "OPENAI_API_KEY": master,
                "ENABLE_OLLAMA_API": "false",
                "RAG_EMBEDDING_ENGINE": "ollama",
                "RAG_EMBEDDING_MODEL": profile["models"].get("embed") or "nomic-embed-text",
                "RAG_OLLAMA_BASE_URL": f"http://127.0.0.1:{p['ollama']}",
                "ENABLE_EVALUATION_ARENA_MODELS": "false",
            },
        }
    return out


def _pid_file(profile: dict, svc: str) -> Path:
    return run_dir(profile) / "pids" / f"{svc}.pid"


# Pids are reused, so a pid file is trusted (and killed) only when the live process is the same process instance that
# was started: pid files record the process start time (Windows creation FILETIME, Linux /proc starttime ticks, ps
# lstart elsewhere), and a pid counts as the service only while a process with that pid AND that start time exists.
# Paths alone are not enough: every `uv run` shares one uv.exe path, and on Linux a venv's python resolves to a shared
# base interpreter. Pid files from before start times were recorded fall back to these launcher names.
EXPECTED_IMAGES = {
    "phoenix": ("phoenix",),
    "litellm": ("litellm",),
    "orchestrator": ("uv",),
    "open_webui": ("open-webui",),
}
# Asks Windows to start the service outside the launching shell's job object. Windows refuses it when the job
# forbids breakaway; start() then retries without. Observed 2026-10-25: services started this way once stopped and
# once survived the end of the Claude Code session that started them, so persistence across sessions is not assured.
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def _proc_info(pid: int) -> tuple[str | None, str | None]:
    """(executable path, start-time token) of a running process; (None, None) when no such process is running.
    Either part may be None when the platform will not report it (e.g. another user's /proc/<pid>/exe)."""
    if not pid:
        return None, None
    if IS_WINDOWS:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        k32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
        k32.GetProcessTimes.argtypes = (wintypes.HANDLE, *[ctypes.POINTER(wintypes.FILETIME)] * 4)
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None, None
        try:
            code = wintypes.DWORD()
            if not k32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:  # 259 = STILL_ACTIVE
                return None, None
            buf = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buf))
            exe = buf.value if k32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)) else None
            created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
            ok = k32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user))
            started = str((created.dwHighDateTime << 32) | created.dwLowDateTime) if ok else None
            return exe, started
        finally:
            k32.CloseHandle(handle)
    proc = Path(f"/proc/{pid}")
    if proc.exists():
        try:
            stat = (proc / "stat").read_text()
            fields = stat[stat.rindex(")") + 2 :].split()  # fields[0] is field 3 (state); comm may contain spaces
            if fields[0] == "Z":
                return None, None  # zombie: already exited
            started = fields[19]  # field 22: starttime in clock ticks since boot
        except (OSError, ValueError, IndexError):
            return None, None
        try:
            exe = os.readlink(proc / "exe")
        except OSError:
            exe = None
        return exe, started
    out = subprocess.run(["ps", "-p", str(pid), "-o", "lstart="], capture_output=True, text=True).stdout.strip()
    if not out:
        return None, None
    comm = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True).stdout.strip()
    return comm or None, out


def _proc_exe(pid: int) -> str | None:
    return _proc_info(pid)[0]


def _proc_name(pid: int, exe: str | None) -> str:
    """Lower-case program name for the legacy name check (Linux: /proc comm, which names the console script)."""
    try:
        return Path(f"/proc/{pid}/comm").read_text().strip().lower()
    except OSError:
        return Path(exe or "").name.lower().removesuffix(".exe")


def _owned(pid: int, svc: str, started: str | None = None) -> bool:
    """True only when pid is alive AND is the process instance this service started."""
    exe, now_started = _proc_info(pid)
    if not (exe or now_started):
        return False
    if started:
        return now_started == started
    name = _proc_name(pid, exe)  # pid file from before start times were recorded
    return any(name.startswith(img) for img in EXPECTED_IMAGES.get(svc, ()))


def _read_pidfile(pf: Path) -> tuple[int, str | None]:
    """(pid, start-time token) from a pid file "pid / executable / start time"; the token is None for older files."""
    try:
        lines = pf.read_text(encoding="utf-8").splitlines()
        started = lines[2].strip() if len(lines) > 2 else ""
        return int(lines[0].strip() or 0), started or None
    except (OSError, ValueError, IndexError):
        return 0, None


def _write_pidfile(pf: Path, pid: int, exe: str, started: str | None) -> None:
    pf.write_text(f"{pid}\n{exe}\n{started or ''}\n", encoding="utf-8")


def start(profile: dict, services: list[str] | None = None) -> None:
    cmds = commands(profile)
    for svc in services or [s for s in SERVICE_ORDER if s in cmds]:
        if svc not in cmds:
            warn(f"{svc}: not configured on this profile")
            continue
        pf = _pid_file(profile, svc)
        if pf.exists():
            pid, started = _read_pidfile(pf)
            if _owned(pid, svc, started):
                info(f"{svc}: already running (pid {pid})")
                continue
            pf.unlink(missing_ok=True)  # stale: the process is gone or the pid now belongs to something else
        if _http_ok(health_url(profile, svc)):
            info(f"{svc}: something already answers on its port; not starting a second copy")
            continue
        c = cmds[svc]
        log = open(run_dir(profile) / "logs" / f"{svc}.log", "ab")
        kwargs: dict = {"cwd": c["cwd"], "env": c["env"], "stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
        if IS_WINDOWS:
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB
        else:
            kwargs["start_new_session"] = True
        try:
            try:
                proc = subprocess.Popen(c["cmd"], **kwargs)
            except PermissionError:
                if not IS_WINDOWS:
                    raise
                # The launching shell's job forbids breakaway; the service will stop when that shell's job closes.
                kwargs["creationflags"] &= ~CREATE_BREAKAWAY_FROM_JOB
                proc = subprocess.Popen(c["cmd"], **kwargs)
                warn(f"{svc}: could not leave the launching shell's job; it stops when that shell exits")
        except FileNotFoundError:
            warn(f"{svc}: executable not found ({c['cmd'][0]}); run `uv run scripts/stack.py setup` to install tools")
            continue
        except OSError as e:
            # e.g. WinError 4551: Smart App Control / App Control blocked the executable.
            warn(f"{svc}: Windows refused to start {c['cmd'][0]}: {e}. Other services still start; see memory/state.md")
            continue
        exe, started = _proc_info(proc.pid)
        if not started:
            warn(f"{svc}: could not read the process start time; `down` will match it by launcher name only")
        _write_pidfile(pf, proc.pid, exe or os.path.abspath(which(c["cmd"][0]) or c["cmd"][0]), started)
        info(f"{svc}: started pid {proc.pid}  (log: {run_dir(profile) / 'logs' / (svc + '.log')})")


def wait_healthy(profile: dict, services: list[str], timeout: float = 120.0) -> dict[str, bool]:
    deadline = time.time() + timeout
    status = {s: False for s in services}
    while time.time() < deadline and not all(status.values()):
        for s in services:
            if not status[s]:
                status[s] = _http_ok(health_url(profile, s))
        if all(status.values()):
            break
        time.sleep(2)
    return status


def stop(profile: dict, services: list[str] | None = None) -> None:
    for svc in services or list(reversed(SERVICE_ORDER)):
        pf = _pid_file(profile, svc)
        if not pf.exists():
            continue
        pid, started = _read_pidfile(pf)
        if pid and not _owned(pid, svc, started):
            other = _proc_exe(pid)
            if other:
                warn(f"{svc}: pid {pid} now belongs to another process ('{other}'); leaving it alone")
            pf.unlink(missing_ok=True)
            continue
        if pid:
            if IS_WINDOWS:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            else:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except OSError:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except OSError:
                        pass  # exited between the ownership check and the kill
            info(f"{svc}: stopped pid {pid}")
        pf.unlink(missing_ok=True)


def status(profile: dict) -> list[dict]:
    rows = []
    for svc in ["ollama", *SERVICE_ORDER]:
        pf = _pid_file(profile, svc)
        pid, started = _read_pidfile(pf) if pf.exists() else (0, None)
        rows.append(
            {
                "service": svc,
                "pid": pid if pid and _owned(pid, svc, started) else None,
                "healthy": _http_ok(health_url(profile, svc)),
                "url": health_url(profile, svc) if svc == "ollama" else health_url(profile, svc).rsplit("/", 1)[0],
            }
        )
    return rows
