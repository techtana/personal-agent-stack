"""Status of the parts the installer sets up that are not services: the Hugging Face cache and OpenClaw.

The tray shows both on its Overview tab. Neither runs under the stack, so a problem with them shows nowhere else: the
cache lives on the models drive, which may be an unplugged USB drive, and OpenClaw counts as private only while the
gateway is its only model endpoint (AGENTS.md rule 9). Each check returns a `ClientStatus` whose level is "ok",
"warn", "bad" or "off" (not set up by choice, nothing to fix). `setup_openclaw` makes the gateway OpenClaw's only
model endpoint, onboarding it first when it has no config.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from . import AGENTS_DIR, IS_WINDOWS, env_value, which

LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}
PROVIDER = "agent-stack"  # the models.providers id `setup_openclaw` writes
DEFAULT_ALIAS = "app-dev"  # the department router OpenClaw starts on; the others are switchable with /model
FIX = "Use gateway in the tray, or `uv run scripts/stack.py openclaw`,"  # how the owner applies setup_openclaw
MODEL_SLOTS = ("imageModel", "utilityModel", "pdfModel")  # agents.defaults slots that may name their own provider
OLLAMA_DEFAULT = "http://127.0.0.1:11434"  # OpenClaw's built-in ollama provider without a models.providers entry
HF_CACHE_DIRS = ("hub", "xet", "datasets", "assets")


@dataclass
class ClientStatus:
    level: str   # "ok" | "warn" | "bad" | "off"
    state: str   # a few words for the row
    detail: str  # one sentence: where it is, or what to do


def user_env(name: str) -> str:
    """The persisted user variable (HKCU\\Environment on Windows), so a value the installer set after this process
    started is seen; falls back to this process's environment."""
    if IS_WINDOWS:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value, _ = winreg.QueryValueEx(key, name)
                if value:
                    return os.path.expandvars(str(value))
        except OSError:
            pass
    return os.environ.get(name, "")


def dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size  # lstat: hub snapshots are symlinks to blobs
            except OSError:
                pass
    return total


def gb(n: int) -> str:
    return f"{n / 1024 ** 3:.1f} GB" if n >= 1024 ** 3 / 10 else f"{n / 1024 ** 2:.0f} MB"


def huggingface(measure_size: bool = True) -> ClientStatus:
    home = user_env("HF_HOME")
    hf = " The hf command is not installed." if not which("hf") else ""
    if not home:
        return ClientStatus("off", "Default cache", "HF_HOME is not set, so Hugging Face downloads go to "
                            f"{Path.home() / '.cache' / 'huggingface'}.{hf}")
    path = Path(home)
    anchor = Path(path.anchor) if path.anchor else None
    if anchor and not anchor.exists():
        return ClientStatus("bad", "Drive missing", f"HF_HOME is {path}, but drive {path.drive or anchor} is not "
                            "connected. Hugging Face downloads fail until it is.")
    if not path.exists():
        return ClientStatus("ok", "Empty", f"{path}: nothing downloaded yet.{hf}")
    size = sum(dir_size(path / d) for d in HF_CACHE_DIRS) if measure_size else None
    used = f"{gb(size)} in " if size is not None else ""
    return ClientStatus("warn" if hf else "ok", gb(size) if size is not None else "Set", f"{used}{path}.{hf}")


# ---------------------------------------------------------------- OpenClaw

def openclaw_config_path() -> Path:
    return Path(os.environ.get("OPENCLAW_CONFIG_PATH") or Path.home() / ".openclaw" / "openclaw.json")


_JSON5_TOKEN = re.compile(r"""
    (?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
  | (?P<comment>//[^\n]*|/\*.*?\*/)
  | (?P<comma>,(?=\s*(?://[^\n]*\s*|/\*.*?\*/\s*)*[}\]]))
  | (?P<key>(?<=[{,\s])[A-Za-z_$][\w$]*(?=\s*:))
""", re.S | re.X)


def loads_json5(text: str):
    """The JSON5 that openclaw.json uses: comments, trailing commas, unquoted keys and single-quoted strings."""
    def fix(m: re.Match) -> str:
        if m.group("str"):
            s = m.group("str")
            return s if s[0] == '"' else json.dumps(json.loads('"' + s[1:-1].replace('\\\'', "'").replace('"', '\\"') + '"'))
        if m.group("key"):
            return f'"{m.group("key")}"'
        return ""
    return json.loads(_JSON5_TOKEN.sub(fix, text))


def model_refs(config: dict) -> set[str]:
    """Every "provider/model" the agents may call: each `model` or `*Model` key under `agents` (a string, a list, or
    {primary, fallbacks})."""
    refs: set[str] = set()

    def add(v) -> None:
        if isinstance(v, str) and "/" in v:
            refs.add(v)
        elif isinstance(v, list):
            for x in v:
                add(x)
        elif isinstance(v, dict):
            add(v.get("primary"))
            add(v.get("fallbacks"))

    def walk(node) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "model" or k.endswith("Model"):
                    add(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for x in node:
                walk(x)
    walk(config.get("agents") or {})
    return refs


def endpoint_kind(url: str, gateway_port: int) -> str:
    """"gateway", "local" (this machine, not the gateway) or "external"."""
    try:
        u = urlsplit(url if "//" in url else "http://" + url)
        host, port = (u.hostname or "").lower(), u.port
    except ValueError:
        return "external"
    if host not in LOOPBACK:
        return "external"
    return "gateway" if port == gateway_port else "local"


def ref_kind(config: dict, ref: str, gateway_port: int) -> str:
    """Where a "provider/model" ref sends prompts: "gateway", "local" or "external". A provider without a
    models.providers entry is one of OpenClaw's built-in cloud providers, except ollama (local by default)."""
    provider = ref.split("/", 1)[0]
    entry = ((config.get("models") or {}).get("providers") or {}).get(provider) or {}
    url = entry.get("baseUrl") or entry.get("baseURL") or (OLLAMA_DEFAULT if provider == "ollama" else "")
    return endpoint_kind(url, gateway_port) if url else "external"


def openclaw(gateway_port: int = 4000) -> ClientStatus:
    if not which("openclaw"):
        return ClientStatus("off", "Not installed", "Optional. The installer can add it (Install OpenClaw).")
    path = openclaw_config_path()
    if not path.exists():
        return ClientStatus("warn", "Not set up", f"Installed but not onboarded. {FIX} sets it up with this stack "
                            "as its only model provider.")
    try:
        config = loads_json5(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return ClientStatus("warn", "Unreadable config", f"Could not read {path} ({e}), so its model endpoints "
                            "are unknown.")
    refs = model_refs(config)
    if not refs:
        return ClientStatus("warn", "No model chosen", f"{path} names no model under agents. {FIX} sets the "
                            "gateway as its model.")
    kinds: dict[str, list[str]] = {"gateway": [], "local": [], "external": []}
    for ref in sorted(refs):
        kinds[ref_kind(config, ref, gateway_port)].append(ref)
    if kinds["external"]:
        return ClientStatus("bad", "Uses an outside model", f"Prompts to {', '.join(kinds['external'])} leave this "
                            f"machine, past the gateway's privacy gate. {FIX} points every model at the gateway.")
    if kinds["local"]:
        return ClientStatus("warn", "Bypasses the gateway", f"{', '.join(kinds['local'])} talks to a local server "
                            f"directly, so it skips the gateway's traces and policy. {FIX} fixes it.")
    return ClientStatus("ok", "Gateway only", f"Every model it calls goes through the gateway ({', '.join(sorted(refs))}). "
                        "Open it with `openclaw dashboard` or `openclaw chat`.")


# ---------------------------------------------------------------- OpenClaw setup

def gateway_aliases() -> list[str]:
    """The aliases OpenClaw may use: the department routers (app-dev first) and local-primary."""
    depts = sorted(p.stem for p in AGENTS_DIR.glob("*.yaml") if not p.stem.startswith("_"))
    return sorted(depts, key=lambda a: a != DEFAULT_ALIAS) + ["local-primary"]


def gateway_patch(config: dict, profile: dict) -> dict:
    """The `openclaw config patch` object that makes the gateway OpenClaw's only model endpoint: the agent-stack
    provider, its models as the default with no fallbacks, and null (delete) for every other model slot or per-agent
    model that points past the gateway. Other providers' entries stay, unused."""
    port = profile["ports"]["litellm"]
    ctx = int(profile["models"].get("primary_num_ctx") or 32768)
    aliases = gateway_aliases()

    def model(alias: str) -> dict:
        return {"id": alias, "name": f"{alias} (Agent Stack)", "contextWindow": ctx, "maxTokens": min(8192, ctx // 4),
                "input": ["text"], "reasoning": False, "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}}

    def off_gateway(value) -> bool:
        return any(ref_kind(config, r, port) != "gateway" for r in model_refs({"agents": {"model": value}}))

    agents = config.get("agents") or {}
    defaults: dict = {"model": {"primary": f"{PROVIDER}/{aliases[0]}", "fallbacks": []},
                      "models": {f"{PROVIDER}/{a}": {} for a in aliases}}
    for slot in MODEL_SLOTS:
        if off_gateway((agents.get("defaults") or {}).get(slot)):
            defaults[slot] = None
    patch: dict = {"agents": {"defaults": defaults},
                   "models": {"providers": {PROVIDER: {
                       "baseUrl": f"http://127.0.0.1:{port}/v1", "api": "openai-completions",
                       "apiKey": {"source": "env", "provider": "default", "id": "LITELLM_MASTER_KEY"},
                       "models": [model(a) for a in aliases]}}}}
    entries = {aid: {"model": None} for aid, e in (agents.get("entries") or {}).items()
               if isinstance(e, dict) and e.get("model") is not None and off_gateway(e["model"])}
    if entries:
        patch["agents"]["entries"] = entries
    return patch


def set_env_line(path: Path, name: str, value: str) -> None:
    """Set NAME=value in a .env file, keeping its other lines."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [ln for ln in lines if not re.match(rf"\s*{re.escape(name)}\s*=", ln)] + [f"{name}={value}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _openclaw_cmd() -> list[str]:
    """OpenClaw's entry script under node: npm's Windows shim is a .cmd, and cmd.exe would mangle JSON arguments."""
    exe = which("openclaw")
    if not exe:
        raise RuntimeError("OpenClaw is not installed")
    script = Path(exe).parent / "node_modules" / "openclaw" / "openclaw.mjs"
    node = which("node")
    return [node, str(script)] if IS_WINDOWS and node and script.exists() else [exe]


def _run(args: list[str], report, what: str, stdin: str | None = None, env: dict | None = None) -> None:
    report(what)
    r = subprocess.run(_openclaw_cmd() + args, input=stdin, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", check=False, timeout=300,
                       env={**os.environ, "OPENCLAW_NO_AUTO_UPDATE": "1", **(env or {})},
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode:
        tail = " ".join((r.stderr or r.stdout).strip().splitlines()[-3:])
        raise RuntimeError(f"`openclaw {' '.join(args[:2])}` exited with code {r.returncode}: {tail}")


def setup_openclaw(profile: dict, report=lambda _msg: None) -> str:
    """Point OpenClaw at the gateway and nothing else. When it has no config yet, onboard it first, non-interactively:
    a workspace and a loopback-only OpenClaw gateway; no daemon, channels, skills, hooks or web search. The gateway
    key goes into ~/.openclaw/.env, which OpenClaw reads; openclaw.json only names it. OpenClaw keeps a backup of the
    config each change replaces (openclaw.json.bak)."""
    key = env_value("LITELLM_MASTER_KEY")
    if not key:
        raise RuntimeError("LITELLM_MASTER_KEY is not in .env; run setup first")
    port = profile["ports"]["litellm"]
    path = openclaw_config_path()
    if not path.exists():
        _run(["onboard", "--non-interactive", "--accept-risk", "--mode", "local", "--flow", "quickstart",
              "--auth-choice", "custom-api-key", "--custom-provider-id", PROVIDER,
              "--custom-base-url", f"http://127.0.0.1:{port}/v1", "--custom-model-id", DEFAULT_ALIAS,
              "--custom-text-input", "--secret-input-mode", "ref", "--gateway-bind", "loopback",
              "--skip-daemon", "--skip-health", "--skip-channels", "--skip-skills", "--skip-search",
              "--skip-hooks", "--skip-ui", "--json"],
             report, "onboarding OpenClaw (no daemon, channels or skills)", env={"CUSTOM_API_KEY": key})
    config = loads_json5(path.read_text(encoding="utf-8"))
    set_env_line(Path.home() / ".openclaw" / ".env", "LITELLM_MASTER_KEY", key)
    _run(["config", "patch", "--stdin", "--replace-path", f"models.providers.{PROVIDER}"], report,
         f"pointing OpenClaw at the gateway (port {port})", stdin=json.dumps(gateway_patch(config, profile)),
         env={"LITELLM_MASTER_KEY": key})
    status = openclaw(port)
    if status.level != "ok":
        raise RuntimeError(f"still not private after setup: {status.state}. {status.detail}")
    return (f"OpenClaw uses only the gateway ({PROVIDER}/{DEFAULT_ALIAS}; /model switches department). "
            "Open it with `openclaw dashboard` or `openclaw chat`.")
