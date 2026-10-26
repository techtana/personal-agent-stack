"""Generate infrastructure/litellm/config.yaml from the machine profile and agents/*.yaml."""
from __future__ import annotations

import yaml

from . import LITELLM_DIR, REPO, info
from .agents_build import load_agents

TIERS = {"simple": "SIMPLE", "medium": "MEDIUM", "complex": "COMPLEX", "reasoning": "REASONING"}
LOCAL_INFO = {"input_cost_per_token": 0, "output_cost_per_token": 0, "supports_function_calling": True, "supports_vision": False}
CLOUD_INFO = {"max_input_tokens": 200000, "max_output_tokens": 32000}


def _ollama(model: str, base: str, **params) -> dict:
    return {"model": f"ollama_chat/{model}", "api_base": base, **params}


def build_config(profile: dict) -> str:
    m = profile["models"]
    base = f"http://127.0.0.1:{profile['ports']['ollama']}"
    cloud = profile["cloud_enabled"]
    cm = profile["cloud_models"]
    key = f"os.environ/{profile['cloud_key_env']}"
    model_list: list[dict] = []
    available: set[str] = set()

    def add(name: str, params: dict, info_: dict, location: str) -> None:
        model_info = {**info_, "agent_stack_location": location}
        model_list.append({"model_name": name, "litellm_params": params, "model_info": model_info})
        available.add(name)

    if m.get("fim"):
        add("local-fim", {"model": f"ollama/{m['fim']}", "api_base": base, "keep_alive": -1},
            {"mode": "completion", "input_cost_per_token": 0, "output_cost_per_token": 0, "max_input_tokens": 4096},
            "local")
    if m.get("embed"):
        add("local-embed", {"model": f"ollama/{m['embed']}", "api_base": base},
            {"mode": "embedding", "input_cost_per_token": 0, "output_cost_per_token": 0},
            "local")
    if m.get("small"):
        add("local-small", _ollama(m["small"], base, num_ctx=m["small_num_ctx"], keep_alive="30m"),
            {**LOCAL_INFO, "max_input_tokens": m["small_num_ctx"], "max_output_tokens": 8192}, "local")
    primary_opts = m.get("primary_options") or {}
    if m.get("primary"):
        add("local-primary", _ollama(m["primary"], base, num_ctx=m["primary_num_ctx"], keep_alive=-1, **primary_opts),
            {**LOCAL_INFO, "max_input_tokens": m["primary_num_ctx"], "max_output_tokens": 8192}, "local")
    if m.get("reviewer"):
        add("local-reviewer", _ollama(m["reviewer"], base, num_ctx=m["primary_num_ctx"], keep_alive="10m", **(m.get("reviewer_options") or {})),
            {**LOCAL_INFO, "max_input_tokens": m["primary_num_ctx"], "max_output_tokens": 8192}, "local")
    if cloud:
        for tier, model in cm.items():
            add(f"cloud-{tier}", {"model": f"anthropic/{model}", "api_key": key}, dict(CLOUD_INFO), "cloud")

    local_default = "local-primary" if "local-primary" in available else ("local-small" if "local-small" in available else None)

    def resolve(target: str) -> str | None:
        if target in available:
            return target
        return local_default  # cloud-* or missing local-* targets fall back to the best local deployment

    agents = load_agents()
    for a in agents:
        aid = a["id"]
        r = a.get("routing") or {}
        if m.get("primary"):
            # Same model and load options as local-primary so Ollama reuses one runner instead of reloading per department.
            add(f"{aid}-local", _ollama(m["primary"], base, num_ctx=m["primary_num_ctx"], keep_alive=-1, **primary_opts, **(a.get("local") or {})),
                {**LOCAL_INFO, "max_input_tokens": m["primary_num_ctx"], "max_output_tokens": 8192}, "local")
        if cloud:
            target = r.get("complex", "cloud-default")
            cloud_model = cm.get(target.replace("cloud-", ""), cm["default"]) if target.startswith("cloud-") else cm["default"]
            add(f"{aid}-cloud", {"model": f"anthropic/{cloud_model}", "api_key": key}, dict(CLOUD_INFO), "cloud")
        tiers = {}
        for low, up in TIERS.items():
            tgt = resolve(r.get(low, "local-primary"))
            if tgt:
                tiers[up] = tgt
        if not tiers:
            continue
        cfg = {
            "tiers": tiers,
            "default_model": tiers.get("MEDIUM") or next(iter(tiers.values())),
            "classifier_type": "heuristic",
            "escalation_keywords": ["ESCALATE", "use claude"],
            "stall_escalation_enabled": True,
            "stall_escalation_window": 6,
            "stall_escalation_repeat_threshold": 2,
            "enable_context_window_escalation": True,
            "context_window_escalation_buffer": 0.9,
            "route_housekeeping_to_cheapest_tier": True,
            "context_compaction": False,
        }
        if r.get("plan_mode_min_tier"):
            cfg["plan_mode_min_tier"] = TIERS[r["plan_mode_min_tier"]]
        if r.get("keyword_tier_rules"):
            cfg["keyword_tier_rules"] = [{"keywords": k["keywords"], "tier": TIERS[k["tier"]]} for k in r["keyword_tier_rules"]]
        model_list.append({"model_name": aid, "litellm_params": {"model": "auto_router/complexity_router", "complexity_router_config": cfg}})

    router_settings: dict = {"routing_strategy": "simple-shuffle", "num_retries": 1, "allowed_fails": 2, "cooldown_time": 30}
    cw = []
    if cloud:
        router_settings["default_fallbacks"] = ["cloud-default"]
        if "local-primary" in available:
            cw.append({"local-primary": ["cloud-default"]})
    if "local-small" in available and "local-primary" in available:
        cw.append({"local-small": ["local-primary"]})
    if cw:
        router_settings["context_window_fallbacks"] = cw

    callbacks = []
    if profile["observability"].get("jsonl_traces", True):
        callbacks.append("custom_callbacks.proxy_handler_instance")
    if profile["observability"].get("phoenix"):
        callbacks.append("otel")
    doc = {
        "model_list": model_list,
        "router_settings": router_settings,
        "litellm_settings": {"drop_params": True, "request_timeout": 600, "callbacks": callbacks},
        "general_settings": {"master_key": "os.environ/LITELLM_MASTER_KEY"},
    }
    header = (
        "# GENERATED by `uv run scripts/stack.py build` from machines/_defaults.yaml, machines/<host>.yaml and agents/*.yaml.\n"
        f"# machine={profile['name']} class={profile['hardware_class']} cloud={'on' if cloud else 'off (no API key)'}\n"
        "# Department aliases: <id> (complexity router), <id>-local, <id>-cloud. Tier targets: local-small, local-primary, cloud-*.\n"
        "# Never pass temperature/top_p/top_k to anthropic/* deployments (HTTP 400 since 2026-10-21); drop_params handles stray client params.\n"
    )
    return header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120)


def build(profile: dict):
    LITELLM_DIR.mkdir(parents=True, exist_ok=True)
    out = LITELLM_DIR / "config.yaml"
    out.write_text(build_config(profile), encoding="utf-8", newline="\n")
    info(f"litellm: wrote {out.relative_to(REPO)}")
    return out
