"""Start/stop/status for the native services (LiteLLM, Phoenix, orchestrator MCP, Open WebUI)."""
from __future__ import annotations

import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import IS_WINDOWS, LITELLM_DIR, REPO, TRACES_DIR, env_value, info, load_dotenv, warn, which

SERVICE_ORDER = ["phoenix", "litellm", "orchestrator", "open_webui"]


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
            "cmd": [which("phoenix") or "phoenix", "serve"],
            "cwd": str(REPO),
            "env": {**base_env, "PHOENIX_PORT": str(p["phoenix"]), "PHOENIX_GRPC_PORT": str(p["phoenix_grpc"]), "PHOENIX_HOST": "127.0.0.1", "PHOENIX_WORKING_DIR": str(d / "phoenix")},
        }
    litellm_env = {**base_env, "LITELLM_MASTER_KEY": master, "TRACES_DIR": str(TRACES_DIR / "litellm"), "LITELLM_LOG": "INFO"}
    if profile["observability"].get("phoenix"):
        litellm_env.update({"OTEL_EXPORTER": "otlp_http", "OTEL_ENDPOINT": f"http://127.0.0.1:{p['phoenix']}/v1/traces", "OTEL_SERVICE_NAME": "litellm"})
    out["litellm"] = {
        "cmd": [which("litellm") or "litellm", "--config", str(LITELLM_DIR / "config.yaml"), "--host", "127.0.0.1", "--port", str(p["litellm"])],
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
            "cmd": [which("open-webui") or "open-webui", "serve", "--host", "127.0.0.1", "--port", str(p["open_webui"])],
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


def _alive(pid: int) -> bool:
    if not pid:
        return False
    if IS_WINDOWS:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start(profile: dict, services: list[str] | None = None) -> None:
    cmds = commands(profile)
    for svc in services or [s for s in SERVICE_ORDER if s in cmds]:
        if svc not in cmds:
            warn(f"{svc}: not configured on this profile")
            continue
        pf = _pid_file(profile, svc)
        if pf.exists() and _alive(int(pf.read_text() or 0)):
            info(f"{svc}: already running (pid {pf.read_text().strip()})")
            continue
        if _http_ok(health_url(profile, svc)):
            info(f"{svc}: something already answers on its port; not starting a second copy")
            continue
        c = cmds[svc]
        log = open(run_dir(profile) / "logs" / f"{svc}.log", "ab")
        kwargs: dict = {"cwd": c["cwd"], "env": c["env"], "stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
        if IS_WINDOWS:
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        try:
            proc = subprocess.Popen(c["cmd"], **kwargs)
        except FileNotFoundError:
            warn(f"{svc}: executable not found ({c['cmd'][0]}); run `uv run scripts/stack.py setup` to install tools")
            continue
        pf.write_text(str(proc.pid))
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
        pid = int(pf.read_text() or 0)
        if pid and _alive(pid):
            if IS_WINDOWS:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            else:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except OSError:
                    os.kill(pid, signal.SIGTERM)
            info(f"{svc}: stopped pid {pid}")
        pf.unlink(missing_ok=True)


def status(profile: dict) -> list[dict]:
    rows = []
    for svc in ["ollama", *SERVICE_ORDER]:
        pf = _pid_file(profile, svc)
        pid = int(pf.read_text() or 0) if pf.exists() else None
        rows.append(
            {
                "service": svc,
                "pid": pid if pid and _alive(pid) else None,
                "healthy": _http_ok(health_url(profile, svc)),
                "url": health_url(profile, svc) if svc == "ollama" else health_url(profile, svc).rsplit("/", 1)[0],
            }
        )
    return rows
