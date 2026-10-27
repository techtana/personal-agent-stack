"""Environment for Claude Code profile B (local gateway) and the per-machine settings.local.json."""
from __future__ import annotations

import json
from pathlib import Path

from . import REPO, die, env_value, load_dotenv

PRIVATE_ALIASES = ("local-small", "local-primary", "local-reviewer")
DENIED_TOOLS = ["WebFetch", "WebSearch"]


def local_profile_env(profile: dict) -> dict[str, str]:
    """Variables that point one Claude Code process at LiteLLM. A credential variable replaces subscription
    billing for that process, which is the point: this profile spends local tokens, not plan quota."""
    cc = profile["claude_code"]
    lp = cc["local_profile"]
    for k in ("default_model", "haiku_model", "sonnet_model", "opus_model"):
        if lp.get(k, "local-primary") not in PRIVATE_ALIASES:
            die(f"claude_code.local_profile.{k} = {lp[k]!r}: profile B uses private aliases only ({', '.join(PRIVATE_ALIASES)})")
    port = profile["ports"]["litellm"]
    master = env_value("LITELLM_MASTER_KEY", load_dotenv())
    cfg_dir = str(Path(cc.get("local_profile_dir", "~/.claude-local")).expanduser())
    ctx = profile["models"]["primary_num_ctx"] or 32768
    return {
        "CLAUDE_CONFIG_DIR": cfg_dir,
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
        "ANTHROPIC_AUTH_TOKEN": master,
        "ANTHROPIC_API_KEY": "",
        "ANTHROPIC_MODEL": lp.get("default_model", "local-primary"),
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": lp.get("haiku_model", "local-small"),
        "ANTHROPIC_DEFAULT_SONNET_MODEL": lp.get("sonnet_model", "local-primary"),
        "ANTHROPIC_DEFAULT_OPUS_MODEL": lp.get("opus_model", "local-primary"),
        "CLAUDE_CODE_SUBAGENT_MODEL": lp.get("default_model", "local-primary"),
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": str(ctx),
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(lp.get("max_output_tokens", 8192)),
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW": str(max(100000, ctx)),
        "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
        "CLAUDE_CODE_GATEWAY_HINT_HEADERS": "1",
        "CLAUDE_CODE_DISABLE_1M_CONTEXT": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }


def write_local_profile_settings(profile: dict) -> Path:
    """Deny the web tools in profile B's own settings.json: they would fetch outside the gateway."""
    p = Path(profile["claude_code"].get("local_profile_dir", "~/.claude-local")).expanduser() / "settings.json"
    doc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    deny = doc.setdefault("permissions", {}).setdefault("deny", [])
    deny += [t for t in DENIED_TOOLS if t not in deny]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return p


def render(env: dict[str, str], shell: str) -> str:
    if shell == "powershell":
        return "\n".join(f"$env:{k} = '{v}'" for k, v in env.items())
    return "\n".join(f"export {k}={json.dumps(v)}" for k, v in env.items())


def write_settings_local(profile: dict) -> Path:
    """Merge machine-specific values into .claude/settings.local.json (gitignored)."""
    p = REPO / ".claude" / "settings.local.json"
    doc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    env = doc.setdefault("env", {})
    dotenv = load_dotenv()
    env["ORCHESTRATOR_BEARER"] = env_value("ORCHESTRATOR_BEARER", dotenv)
    env["LITELLM_MASTER_KEY"] = env_value("LITELLM_MASTER_KEY", dotenv)
    # autoMemoryDirectory accepts absolute or ~/ paths only (settings reference); keep auto memory in the repo.
    doc["autoMemoryDirectory"] = str(REPO / "memory" / "claude")
    doc.setdefault("enabledMcpjsonServers", ["orchestrator"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return p
