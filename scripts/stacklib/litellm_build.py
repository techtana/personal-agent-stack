"""Generate infrastructure/litellm/config.yaml from the machine profile and agents/*.yaml."""
from __future__ import annotations

import yaml

from . import LITELLM_DIR, REPO, die, info
from .agents_build import load_agents

TIERS = {"simple": "SIMPLE", "medium": "MEDIUM", "complex": "COMPLEX", "reasoning": "REASONING"}
LOCAL_INFO = {"input_cost_per_token": 0, "output_cost_per_token": 0, "supports_function_calling": True, "supports_vision": False}
PRIVATE_TARGETS = ("local-small", "local-primary", "local-reviewer")


def _ollama(model: str, base: str, **params) -> dict:
    return {"model": f"ollama_chat/{model}", "api_base": base, **params}


def build_config(profile: dict) -> str:
    m = profile["models"]
    base = f"http://127.0.0.1:{profile['ports']['ollama']}"
    policy = profile["policy"]
    if policy["external"]["enabled"]:
        die("policy/privacy.yaml: external.enabled is true, but the privacy guardrail and gate (packages S1-S3) are not "
            "built yet; external models stay off until they are")
    private = {"data_class": "private", "location": policy["location"]}
    model_list: list[dict] = []
    available: set[str] = set()

    def add(name: str, params: dict, info_: dict) -> None:
        model_list.append({"model_name": name, "litellm_params": params, "model_info": {**info_, **private}})
        available.add(name)

    if m.get("fim"):
        add("local-fim", {"model": f"ollama/{m['fim']}", "api_base": base, "keep_alive": -1},
            {"mode": "completion", "input_cost_per_token": 0, "output_cost_per_token": 0, "max_input_tokens": 4096})
    if m.get("embed"):
        add("local-embed", {"model": f"ollama/{m['embed']}", "api_base": base},
            {"mode": "embedding", "input_cost_per_token": 0, "output_cost_per_token": 0})
    if m.get("small"):
        add("local-small", _ollama(m["small"], base, num_ctx=m["small_num_ctx"], keep_alive="30m"),
            {**LOCAL_INFO, "max_input_tokens": m["small_num_ctx"], "max_output_tokens": 8192})
    primary_opts = m.get("primary_options") or {}
    if m.get("primary"):
        add("local-primary", _ollama(m["primary"], base, num_ctx=m["primary_num_ctx"], keep_alive=-1, **primary_opts),
            {**LOCAL_INFO, "max_input_tokens": m["primary_num_ctx"], "max_output_tokens": 8192})
    if m.get("reviewer"):
        add("local-reviewer", _ollama(m["reviewer"], base, num_ctx=m["primary_num_ctx"], keep_alive="10m", **(m.get("reviewer_options") or {})),
            {**LOCAL_INFO, "max_input_tokens": m["primary_num_ctx"], "max_output_tokens": 8192})
    local_default = "local-primary" if "local-primary" in available else ("local-small" if "local-small" in available else None)

    def resolve(aid: str, target: str) -> str | None:
        if target not in PRIVATE_TARGETS:
            die(f"agents/{aid}.yaml: routing target {target!r} is not a private deployment ({', '.join(PRIVATE_TARGETS)})")
        return target if target in available else local_default  # a model this machine lacks -> best local one

    agents = load_agents()
    for a in agents:
        aid = a["id"]
        r = a.get("routing") or {}
        if m.get("primary"):
            # Same model and load options as local-primary so Ollama reuses one runner instead of reloading per department.
            add(f"{aid}-local", _ollama(m["primary"], base, num_ctx=m["primary_num_ctx"], keep_alive=-1, **primary_opts, **(a.get("local") or {})),
                {**LOCAL_INFO, "max_input_tokens": m["primary_num_ctx"], "max_output_tokens": 8192})
        tiers = {}
        for low, up in TIERS.items():
            tgt = resolve(aid, r.get(low, "local-primary"))
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
        model_list.append({"model_name": aid, "litellm_params": {"model": "auto_router/complexity_router", "complexity_router_config": cfg},
                           "model_info": dict(private)})

    router_settings: dict = {"routing_strategy": "simple-shuffle", "num_retries": 1, "allowed_fails": 2, "cooldown_time": 30}
    cw = []
    if "local-small" in available and "local-primary" in available:
        cw.append({"local-small": ["local-primary"]})
    if cw:
        router_settings["context_window_fallbacks"] = cw

    callbacks = []
    if profile["observability"].get("jsonl_traces", True):
        callbacks.append("custom_callbacks.proxy_handler_instance")
    if profile["observability"].get("phoenix"):
        callbacks.append("otel")
    check_private(model_list, router_settings)
    doc = {
        "model_list": model_list,
        "router_settings": router_settings,
        "litellm_settings": {"drop_params": True, "request_timeout": 600, "callbacks": callbacks},
        "general_settings": {"master_key": "os.environ/LITELLM_MASTER_KEY"},
    }
    header = (
        "# GENERATED by `uv run scripts/stack.py build` from machines/*.yaml, agents/*.yaml and policy/privacy.yaml.\n"
        f"# machine={profile['name']} class={profile['hardware_class']} external=off\n"
        "# Private first: every deployment carries model_info.data_class; routers and fallbacks use private ones only.\n"
        "# Department aliases: <id> (complexity router over local deployments), <id>-local.\n"
    )
    return header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120)


def check_private(model_list: list[dict], router_settings: dict) -> None:
    """Fail the build if a deployment lacks a data class or anything automatic can reach a non-private one."""
    classes = {}
    for d in model_list:
        mi = d.get("model_info") or {}
        if mi.get("data_class") not in ("private", "external"):
            die(f"litellm: deployment {d['model_name']!r} has no model_info.data_class")
        if mi["data_class"] == "private" and mi.get("location") not in ("onprem", "confidential-cloud"):
            die(f"litellm: private deployment {d['model_name']!r} has no valid model_info.location")
        classes[d["model_name"]] = mi["data_class"]
    refs: list[tuple[str, str]] = []
    for d in model_list:
        cfg = d["litellm_params"].get("complexity_router_config")
        if cfg:
            refs += [(f"{d['model_name']} tier {t}", v) for t, v in cfg["tiers"].items()]
            refs.append((f"{d['model_name']} default", cfg["default_model"]))
    refs += [("default_fallbacks", v) for v in router_settings.get("default_fallbacks", [])]
    for entry in router_settings.get("context_window_fallbacks", []) + router_settings.get("fallbacks", []):
        for src, dsts in entry.items():
            refs += [(f"fallback from {src}", v) for v in dsts]
    for where, target in refs:
        if classes.get(target) != "private":
            die(f"litellm: {where} -> {target!r} is not a private deployment")


def build(profile: dict):
    LITELLM_DIR.mkdir(parents=True, exist_ok=True)
    out = LITELLM_DIR / "config.yaml"
    out.write_text(build_config(profile), encoding="utf-8", newline="\n")
    info(f"litellm: wrote {out.relative_to(REPO)}")
    return out
