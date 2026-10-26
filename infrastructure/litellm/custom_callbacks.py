"""LiteLLM proxy callback: one JSON line per request to $TRACES_DIR/YYYY-MM-DD.jsonl.

This is the dataset the nightly retrospective and `stack.py why-routed` read. It records which
department alias was requested, which deployment served it, the router's decision, tokens, cost and
latency, plus Claude Code's gateway hint headers when present. No prompt or completion text is stored.
Registered in config.yaml as `litellm_settings.callbacks: [custom_callbacks.proxy_handler_instance]`;
the proxy is started with infrastructure/litellm as its working directory so the module resolves.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger

TRACES_DIR = Path(os.environ.get("TRACES_DIR") or Path(__file__).resolve().parents[2] / "traces" / "litellm")


def _hint_headers(slo: dict, kwargs: dict) -> dict:
    md = (slo.get("metadata") or {}) if isinstance(slo, dict) else {}
    hdrs = md.get("requester_custom_headers") or ((kwargs.get("litellm_params") or {}).get("metadata") or {}).get("headers") or {}
    out = {}
    for k, v in (hdrs or {}).items():
        lk = str(k).lower()
        if lk.startswith("x-claude-code-") or lk == "user-agent":
            out[lk] = v
    return out


def _usage(response_obj) -> dict:
    if isinstance(response_obj, dict):
        return response_obj.get("usage") or {}
    u = getattr(response_obj, "usage", None)
    if not u:
        return {}
    if isinstance(u, dict):
        return u
    if hasattr(u, "model_dump"):
        return u.model_dump()
    try:
        return dict(u)
    except (TypeError, ValueError):
        return {}


class TraceLogger(CustomLogger):
    def _write(self, kwargs, response_obj, start_time, end_time, status: str):
        try:
            slo = kwargs.get("standard_logging_object") or {}
            usage = _usage(response_obj)
            hints = _hint_headers(slo, kwargs)
            hidden = slo.get("hidden_params") or {}
            rec = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "status": status,
                "requested_model": slo.get("model_group") or kwargs.get("model"),
                "model": slo.get("model") or kwargs.get("model"),
                "provider": slo.get("custom_llm_provider") or (kwargs.get("litellm_params") or {}).get("custom_llm_provider"),
                "api_base": slo.get("api_base"),
                "call_type": slo.get("call_type") or kwargs.get("call_type"),
                "prompt_tokens": slo.get("prompt_tokens") or usage.get("prompt_tokens") or 0,
                "completion_tokens": slo.get("completion_tokens") or usage.get("completion_tokens") or 0,
                "cost": slo.get("response_cost") or kwargs.get("response_cost") or 0.0,
                "latency_ms": int((end_time - start_time).total_seconds() * 1000) if start_time and end_time else None,
                "cache_hit": slo.get("cache_hit"),
                "routing_decision": slo.get("routing_decision") or hidden.get("routing_decision"),
                "request_class": hints.get("x-claude-code-request-class"),
                "agent_type": hints.get("x-claude-code-agent-type"),
                "user_agent": hints.get("user-agent"),
                "key_alias": (slo.get("metadata") or {}).get("user_api_key_alias"),
                "error": (slo.get("error_str") or str(kwargs.get("exception") or ""))[:300] if status == "failure" else None,
            }
            TRACES_DIR.mkdir(parents=True, exist_ok=True)
            with open(TRACES_DIR / f"{datetime.now().date().isoformat()}.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        except Exception as e:  # noqa: BLE001 - logging must never break the proxy
            print(f"[custom_callbacks] trace write failed: {e}")

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._write(kwargs, response_obj, start_time, end_time, "success")

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        self._write(kwargs, response_obj, start_time, end_time, "failure")


proxy_handler_instance = TraceLogger()
