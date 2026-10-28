"""Generate per-tool agent files from agents/*.yaml (single source of truth)."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from . import AGENTS_DIR, REPO, info

GENERATED_NOTE = "GENERATED from agents/{id}.yaml by `uv run scripts/stack.py build`. Edit the YAML, not this file."


def load_agents() -> list[dict]:
    agents = []
    for p in sorted(AGENTS_DIR.glob("*.yaml")):
        if p.name.startswith("_"):
            continue
        a = yaml.safe_load(p.read_text(encoding="utf-8"))
        a["_path"] = p
        agents.append(a)
    return agents


def common_footer() -> str:
    p = AGENTS_DIR / "_common.md"
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def full_prompt(agent: dict) -> str:
    return agent["system_prompt"].rstrip() + "\n\n" + common_footer() + "\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def build_claude_agent(agent: dict) -> str:
    c = agent.get("claude", {})
    fm = [f"name: {agent['id']}", f"description: {json.dumps(agent['description'].strip())}"]
    if agent.get("tools"):
        fm.append("tools: " + ", ".join(agent["tools"]))
    fm.append(f"model: {c.get('model', 'sonnet')}")
    if c.get("permission_mode"):
        fm.append(f"permissionMode: {c['permission_mode']}")
    fm.append(f"memory: {c.get('memory', 'project')}")
    if c.get("max_turns"):
        fm.append(f"maxTurns: {c['max_turns']}")
    if c.get("effort"):
        fm.append(f"effort: {c['effort']}")
    if agent.get("color"):
        fm.append(f"color: {agent['color']}")
    return "---\n" + "\n".join(fm) + "\n---\n" + f"<!-- {GENERATED_NOTE.format(id=agent['id'])} -->\n\n" + full_prompt(agent)


def build_opencode_agent(agent: dict) -> str:
    o = agent.get("opencode", {})
    fm = {"description": agent["description"].strip(), "mode": o.get("mode", "subagent"), "model": f"litellm/{agent['id']}"}
    if o.get("permission"):
        fm["permission"] = o["permission"]
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n" + f"<!-- {GENERATED_NOTE.format(id=agent['id'])} -->\n\n" + full_prompt(agent)


def build_openwebui_model(agent: dict) -> list[dict]:
    w = agent.get("openwebui", {})
    return [
        {
            "id": agent["id"],
            "base_model_id": agent["id"],
            "name": agent["name"],
            "meta": {
                "profile_image_url": "/static/favicon.png",
                "description": agent["description"].strip(),
                "capabilities": {
                    "vision": False,
                    "file_upload": True,
                    "web_search": False,
                    "image_generation": False,
                    "code_interpreter": False,
                    "citations": True,
                    "usage": True,
                },
                "suggestion_prompts": [{"content": s} for s in w.get("suggestion_prompts", [])],
                "tags": [{"name": "department"}],
            },
            "params": {"system": full_prompt(agent)},
            "is_active": True,
        }
    ]


def build_promptfoo(agent: dict, master_key_env: str = "LITELLM_MASTER_KEY", port: int = 4000) -> tuple[str, str]:
    prompt_file = json.dumps(
        [{"role": "system", "content": full_prompt(agent)}, {"role": "user", "content": "{{prompt}}"}], indent=2
    )
    cfg = {
        "description": f"{agent['name']} regression gate (local tier via LiteLLM)",
        "prompts": ["file://prompt.json"],
        "providers": [
            {
                "id": f"openai:chat:{agent['id']}-local",
                "label": "local",
                "config": {"apiBaseUrl": f"http://127.0.0.1:{port}/v1", "apiKeyEnvar": master_key_env, "max_tokens": 1500},
            }
        ],
        "tests": [
            {"description": e["name"], "vars": {"prompt": e["prompt"]}, "assert": e.get("assert", [])}
            for e in agent.get("evals", [])
        ],
    }
    return prompt_file, yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True, width=120)


def update_opencode_json(agents: list[dict], profile: dict) -> None:
    p = REPO / "opencode.json"
    doc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"$schema": "https://opencode.ai/config.json", "provider": {}}
    prov = doc.setdefault("provider", {}).setdefault(
        "litellm",
        {
            "npm": "@ai-sdk/openai-compatible",
            "name": "LiteLLM gateway",
            "options": {"baseURL": f"http://127.0.0.1:{profile['ports']['litellm']}/v1", "apiKey": "{env:LITELLM_MASTER_KEY}"},
        },
    )
    ctx = profile["models"]["primary_num_ctx"] or 32768
    models = {a["id"]: {"name": f"{a['name']} (router)", "limit": {"context": ctx, "output": 8192}} for a in agents}
    for a in agents:
        models[f"{a['id']}-local"] = {"name": f"{a['name']} (local only)", "limit": {"context": ctx, "output": 8192}}
    if profile["models"].get("primary"):
        models["local-primary"] = {"name": f"local primary: {profile['models']['primary']}", "limit": {"context": ctx, "output": 8192}}
    if profile["models"].get("small"):
        models["local-small"] = {
            "name": f"local small: {profile['models']['small']}",
            "limit": {"context": profile["models"]["small_num_ctx"], "output": 8192},
        }
    prov["models"] = models
    doc["model"] = "litellm/app-dev"
    doc["small_model"] = "litellm/local-small" if profile["models"].get("small") else "litellm/docs"
    write(p, json.dumps(doc, indent=2) + "\n")


def build_all(profile: dict) -> list[Path]:
    agents = load_agents()
    out: list[Path] = []
    for a in agents:
        paths = {
            REPO / ".claude" / "agents" / f"{a['id']}.md": build_claude_agent(a),
            REPO / ".opencode" / "agents" / f"{a['id']}.md": build_opencode_agent(a),
            REPO / "config" / "openwebui" / f"{a['id']}.json": json.dumps(build_openwebui_model(a), indent=2, ensure_ascii=False) + "\n",
        }
        prompt_json, pf = build_promptfoo(a, port=profile["ports"]["litellm"])
        paths[REPO / "evals" / a["id"] / "prompt.json"] = prompt_json + "\n"
        paths[REPO / "evals" / a["id"] / "promptfooconfig.yaml"] = f"# {GENERATED_NOTE.format(id=a['id'])}\n" + pf
        for p, text in paths.items():
            write(p, text)
            out.append(p)
    update_opencode_json(agents, profile)
    out.append(REPO / "opencode.json")
    info(f"agents: generated {len(out)} files for {len(agents)} departments")
    return out
