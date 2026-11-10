"""Claude's own keys for the stack, and the switch that lets Claude use them.

Claude Code connects to two services the stack runs: the gateway (LiteLLM, profile B through `claude-local`) and the
agent tools (the orchestrator MCP server, through .mcp.json). It gets keys of its own for them, never the stack's:
LITELLM_CLAUDE_KEY for the gateway and ORCHESTRATOR_CLAUDE_BEARER for the agent tools, both in the stack's .env and in
Claude Code's .claude/settings.local.json. The services accept them only while `claude_access.enabled` is true. The
tray's switch (Overview > Claude, Settings > Claude) writes a small switch file that both services read on each
request, so turning Claude off takes effect at the next request, without a restart.

What it cannot stop: every program on this PC can connect to every 127.0.0.1 port, and Claude Code runs commands as
the owner, so it could read the stack's own keys from .env and use them, or turn the switch back on (stack.py
claude-access on, the switch file, the machine profile); Ollama and ComfyUI take no key at all.

The top of this module is standard library only: the gateway (LiteLLM's own environment) and the orchestrator import
Switch from it.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import threading
import time
from pathlib import Path

GATEWAY_KEY = "LITELLM_CLAUDE_KEY"            # Claude's key for the gateway (profile B's ANTHROPIC_AUTH_TOKEN)
TOOLS_KEY = "ORCHESTRATOR_CLAUDE_BEARER"      # Claude's bearer for the agent tools; .mcp.json reads it (never *_TOKEN)
CLAUDE_KEYS = (GATEWAY_KEY, TOOLS_KEY)
STACK_KEYS = ("LITELLM_MASTER_KEY", "ORCHESTRATOR_BEARER")   # the stack's own keys: Claude's settings must not hold them
ALIAS = "claude"                              # key alias in the gateway's traces, client id in the orchestrator
FILE_ENV = "AGENT_STACK_CLAUDE_ACCESS_FILE"   # the switch file, for the services
START_ENV = "AGENT_STACK_CLAUDE_ACCESS"       # the switch when the service started ("1" / "0"), if the file is missing
SWITCH_NAME = "claude-access.json"
OFF_MESSAGE = ("Claude's access to the personal agent stack is turned off. Turn it on in the stack's tray: "
               "Overview > Claude.")


def read_switch(path: Path) -> bool:
    """The switch file's value; False when it cannot be read or holds anything but {"enabled": true}."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get("enabled") is True
    except (OSError, ValueError, AttributeError):
        return False


class Switch:
    """Whether Claude's keys work, for a service: the switch file, read again whenever it changes. A file that was never
    there means the value the service started with; a file that cannot be read, or that went away after it was seen,
    means off until it is written again."""

    def __init__(self, path: str | Path | None, default: bool = True):
        self.path = Path(path) if path else None
        self.default = default
        self._stamp: tuple | None = None
        self._value = default
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls, env=None) -> "Switch":
        env = os.environ if env is None else env
        start = str(env.get(START_ENV, "1")).strip().lower() not in ("0", "false", "no", "off")
        return cls(env.get(FILE_ENV) or None, start)

    def on(self) -> bool:
        if self.path is None:
            return self.default
        try:
            st = self.path.stat()
        except FileNotFoundError:
            return self.default if self._stamp is None else False
        except OSError:
            return False
        stamp = (st.st_mtime_ns, st.st_size, st.st_ino)
        with self._lock:
            if stamp != self._stamp:
                self._value, self._stamp = read_switch(self.path), stamp
            return self._value


# ---------------------------------------------------------------- the profile's side (stack.py, the tray, setup)

def enabled(profile: dict) -> bool:
    """The profile's switch: on when it is not set; otherwise on only for true, 1, "on" or "yes"."""
    value = (profile.get("claude_access") or {}).get("enabled")
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "on", "yes")


def switch_path(profile: dict) -> Path:
    return Path(profile["data_dir"]) / SWITCH_NAME


def write_switch(profile: dict) -> Path:
    """Write the switch file from the profile. The file is replaced whole, so a service never reads half of it; a
    service reading it at that moment can hold it open on Windows, hence the retries."""
    path = switch_path(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"enabled": enabled(profile), "written": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n",
                   encoding="utf-8", newline="\n")
    for attempt in range(20):
        try:
            os.replace(tmp, path)
            return path
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)
    return path


def service_env(profile: dict) -> dict[str, str]:
    """Where the gateway and the agent tools find the switch, and its value when they start."""
    return {FILE_ENV: str(switch_path(profile)), START_ENV: "1" if enabled(profile) else "0"}


def stack_env_file() -> Path:
    """The .env of the stack that runs on this PC: the installed app's when this code runs from a checkout and an app
    is installed; else this folder's, or for a worktree without one, its main checkout's."""
    from . import ENV_FILE, deploy
    from . import profile as prof

    app = deploy.installed_app()
    if app is not None and not deploy.is_app():
        return app / ".env"
    if not ENV_FILE.exists():
        main = prof._main_checkout()
        if main is not None and (main / ".env").exists():
            return main / ".env"
    return ENV_FILE


def read_keys(path: Path | None = None) -> dict[str, str]:
    """Claude's two keys from the stack's .env as they are ("" where missing); nothing is written."""
    from . import load_dotenv

    have = load_dotenv(Path(path) if path else stack_env_file())
    return {k: have.get(k, "") for k in CLAUDE_KEYS}


def new_key(name: str) -> str:
    """A new random value for one of Claude's keys. The gateway's starts with sk- like its master key, so LiteLLM
    hashes it wherever it logs a key."""
    return "sk-claude-" + secrets.token_hex(24) if name == GATEWAY_KEY else secrets.token_urlsafe(32)


def ensure_keys(path: Path | None = None) -> dict[str, str]:
    """Claude's two keys from the stack's .env, appending a new random one for each that is missing; the rest of the
    file is left as it is (comments included). The services read them when they start. The note goes to stderr:
    `stack.py claude-env` prints shell lines that claude-local.ps1 and .sh run."""
    import sys

    from . import load_dotenv

    path = Path(path) if path else stack_env_file()
    have = load_dotenv(path)
    keys = {k: have.get(k, "") for k in CLAUDE_KEYS}
    missing = [k for k in CLAUDE_KEYS if not keys[k]]
    if missing:
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        lines = []
        for k in missing:
            keys[k] = new_key(k)
            lines.append(f"{k}={keys[k]}")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(("" if not text or text.endswith("\n") else "\n") + "\n".join(lines) + "\n")
        print(f"{path.name}: added {', '.join(missing)}, Claude's own keys for the gateway and the agent tools",
              file=sys.stderr, flush=True)
    return keys


def checkouts() -> list[Path]:
    """The folders where Claude Code works on this repository: the checkout this code runs from, its main checkout and
    their worktrees. None in the installed app, which keeps no path back to the checkout it came from: the checkout
    gives Claude Code its keys when it installs the app (stack.py deploy), or with `stack.py claude-access connect`."""
    from . import REPO, deploy

    if deploy.is_app():
        return []
    try:
        out = subprocess.run(["git", "-C", str(REPO), "worktree", "list", "--porcelain"], capture_output=True,
                             text=True, timeout=15, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    roots = [Path(line[len("worktree "):].strip()) for line in out.splitlines() if line.startswith("worktree ")]
    seen, result = set(), []
    for root in roots or [REPO]:
        key = os.path.normcase(str(root.resolve()))
        if key not in seen and root.is_dir():
            seen.add(key)
            result.append(root)
    return result


def settings_file(root: Path) -> Path:
    return Path(root) / ".claude" / "settings.local.json"


def _load(path: Path) -> dict | None:
    """A settings file's JSON object; None when it cannot be read or is not an object."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def give_claude_keys(doc: dict, keys: dict[str, str]) -> bool:
    """Put Claude's keys into a settings.local.json document and take the stack's own keys out. True if it changed."""
    env = doc.get("env") if isinstance(doc.get("env"), dict) else {}
    before = dict(env)
    for k in STACK_KEYS:
        env.pop(k, None)
    env.update({k: v for k, v in keys.items() if v})
    doc["env"] = env
    return env != before


def stack_values(env_file: Path | None = None) -> list[str]:
    """The stack's own key values (to find copies of them anywhere in a settings file, not only under env)."""
    from . import load_dotenv

    have = load_dotenv(Path(env_file) if env_file else stack_env_file())
    return [v for v in (have.get(k, "") for k in STACK_KEYS) if len(v) >= 16]


def write_json(path: Path, doc: dict, expect: str | None = None) -> bool:
    """Replace a JSON file whole (a temporary file, then a rename), so a crash never leaves half a file. With `expect`
    (the text it was read from), give up and return False when the file changed in the meantime, for instance when a
    running Claude Code session saved an allow rule there."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
    try:
        if expect is not None and path.read_text(encoding="utf-8-sig") != expect:
            return False
        os.replace(tmp, path)
        return True
    finally:
        tmp.unlink(missing_ok=True)


def connect(roots: list[Path] | None = None, env_file: Path | None = None) -> list[tuple[Path, str]]:
    """Give Claude Code its own keys in every checkout's .claude/settings.local.json that exists, and take the stack's
    keys out of its env entries; nothing else in the file changes. A copy of a stack key elsewhere in the file (an
    allow rule with a literal bearer, say) is reported, not edited. Returns (file, "updated" | "unchanged" |
    "failed: ..."), with a note when such a copy remains."""
    keys = ensure_keys(env_file)
    secrets_ = stack_values(env_file)
    out = []
    for root in checkouts() if roots is None else roots:
        path = settings_file(root)
        if not path.exists():
            continue
        result = "failed: it kept changing while it was being updated; try again"
        try:
            for _ in range(3):
                text = path.read_text(encoding="utf-8-sig")
                try:
                    doc = json.loads(text)
                except ValueError:
                    doc = None
                if not isinstance(doc, dict):
                    result = "failed: not a JSON object; fix it by hand"
                    break
                if not give_claude_keys(doc, keys):
                    result = "unchanged"
                    break
                if write_json(path, doc, expect=text):
                    result = "updated"
                    break
            if not result.startswith("failed") and any(v in path.read_text(encoding="utf-8-sig") for v in secrets_):
                result += "; a stack key is still written elsewhere in this file: remove it by hand"
        except OSError as e:
            result = f"failed: {e.strerror or e}"
        out.append((path, result))
    return out


def status(profile: dict) -> dict:
    """For the tray and `stack.py claude-access`: the switch, whether the stack's .env has Claude's keys, and which of
    Claude Code's settings files hold Claude's keys or still the stack's own."""
    from . import load_dotenv

    env = load_dotenv(stack_env_file())
    roots = checkouts()
    held = holders(roots)
    return {"enabled": enabled(profile), "keys": all(env.get(k) for k in CLAUDE_KEYS), "checkouts": len(roots),
            "stack": held["stack"], "claude": held["claude"]}


def holders(roots: list[Path] | None = None, env_file: Path | None = None) -> dict[str, list[Path]]:
    """Which Claude settings files hold which keys (names only): {"stack": files with the stack's own keys, under env
    or anywhere else in the file, "claude": files with Claude's keys}."""
    out: dict[str, list[Path]] = {"stack": [], "claude": []}
    secrets_ = stack_values(env_file)
    for root in checkouts() if roots is None else roots:
        path = settings_file(root)
        doc = _load(path) or {}
        env = doc.get("env") if isinstance(doc.get("env"), dict) else {}
        text = json.dumps(doc)
        if any(env.get(k) for k in STACK_KEYS) or any(v in text for v in secrets_):
            out["stack"].append(path)
        if all(env.get(k) for k in CLAUDE_KEYS):
            out["claude"].append(path)
    return out
