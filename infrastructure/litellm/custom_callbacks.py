"""LiteLLM proxy callback: one JSON line per request to $TRACES_DIR/YYYY-MM-DD.jsonl.

This is the dataset the nightly retrospective and `stack.py why-routed` read. It records which
department alias was requested, which deployment served it, the router's decision, tokens, cost and
latency, plus Claude Code's gateway hint headers when present. No prompt or completion text is stored.
Registered in config.yaml as `litellm_settings.callbacks: [custom_callbacks.proxy_handler_instance]`;
the proxy is started with infrastructure/litellm as its working directory so the module resolves.
"""
from __future__ import annotations

import json
import math
import os
import time
from collections.abc import AsyncGenerator, Mapping
from datetime import datetime, timezone
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger
from litellm.types.utils import Delta, ModelResponseStream, StreamingChoices

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


def _raw_response(kwargs: dict) -> dict:
    raw = kwargs.get("original_response")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _duration_ms(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return value / 1_000_000


def _emit_phoenix_metrics(record: dict) -> None:
    if not os.environ.get("OTEL_ENDPOINT"):
        return
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer("personal-agent-stack.metrics")
        common = {
            "agent_stack.model": str(record.get("model") or "unknown"),
            "agent_stack.provider": str(record.get("provider") or "unknown"),
            "agent_stack.prompt_tokens": int(record.get("prompt_tokens") or 0),
            "agent_stack.completion_tokens": int(record.get("completion_tokens") or 0),
            "agent_stack.cost_usd": float(record.get("cost") or 0),
        }
        phases = [("litellm.request", "litellm", record.get("latency_ms"))]
        if record.get("process") == "ollama":
            phases.extend(
                (name, "ollama", record.get(field))
                for name, field in (
                    ("model.load", "model_load_ms"),
                    ("input.prefill", "input_ms"),
                    ("inference.decode", "inference_ms"),
                    ("model.request", "model_total_ms"),
                )
            )
        elif record.get("provider"):
            phases.append(("provider.request", str(record["provider"]), record.get("latency_ms")))

        for operation, process, duration in phases:
            if duration is None:
                continue
            end_ns = time.time_ns()
            start_ns = end_ns - int(float(duration) * 1_000_000)
            span = tracer.start_span(f"agent_stack.{operation}", start_time=max(1, start_ns))
            span.set_attribute("agent_stack.process", process)
            span.set_attribute("agent_stack.operation", operation)
            span.set_attribute("agent_stack.duration_ms", float(duration))
            for key, value in common.items():
                span.set_attribute(key, value)
            span.end(end_time=end_ns)
    except Exception as e:  # noqa: BLE001 - telemetry must never break the proxy
        print(f"[custom_callbacks] Phoenix metric export failed: {e}")


def _deployed_model(data: dict) -> str | None:
    logging_obj = data.get("litellm_logging_obj")
    litellm_params = getattr(logging_obj, "litellm_params", None)
    if not isinstance(litellm_params, Mapping):
        return None
    for metadata_key in ("litellm_metadata", "metadata"):
        metadata = litellm_params.get(metadata_key)
        if isinstance(metadata, Mapping):
            deployment = metadata.get("deployment")
            if isinstance(deployment, str) and deployment:
                return deployment
    return None


def _model_location(data: dict) -> str | None:
    logging_obj = data.get("litellm_logging_obj")
    litellm_params = getattr(logging_obj, "litellm_params", None)
    if not isinstance(litellm_params, Mapping):
        return None
    for metadata_key in ("litellm_metadata", "metadata"):
        metadata = litellm_params.get(metadata_key)
        if not isinstance(metadata, Mapping):
            continue
        model_info = metadata.get("model_info")
        if not isinstance(model_info, Mapping):
            continue
        location = model_info.get("agent_stack_location")
        if location == "local":
            return "Local"
        if location == "cloud":
            return "Cloud"
    return None


def _routing_footer(data: dict) -> str | None:
    for metadata_key in ("litellm_metadata", "metadata"):
        metadata = data.get(metadata_key)
        if not isinstance(metadata, Mapping):
            continue
        decision = metadata.get("routing_decision")
        if not isinstance(decision, Mapping):
            continue
        tier = decision.get("tier_label") or decision.get("tier")
        target = decision.get("routed_model")
        if not tier and not target:
            continue
        model = _deployed_model(data) or (str(target) if target else None)
        location = _model_location(data)
        used = f"**Used:** {model}"
        if location:
            used += f" ({location})"
        route = " -> ".join(str(value) for value in (tier, target) if value)
        cause = decision.get("cause")
        if cause:
            route += f" ({str(cause).replace('_', ' ')})"
        return f"\n\n---\n{used}\n**Route:** {route}"
    return None


def _append_route_footer(response, footer: str) -> bool:
    if isinstance(response, dict):
        choices = response.get("choices")
        message = choices[0].get("message") if choices and isinstance(choices[0], dict) else None
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            return False
        if message.get("tool_calls"):
            return False
        message["content"] += footer
        return True

    choices = getattr(response, "choices", None)
    message = getattr(choices[0], "message", None) if choices else None
    content = getattr(message, "content", None)
    if not isinstance(content, str) or getattr(message, "tool_calls", None):
        return False
    message.content = content + footer
    return True


def _stream_finished_with_tool_call(chunk) -> bool:
    choices = getattr(chunk, "choices", None)
    if not choices:
        return False
    return getattr(choices[0], "finish_reason", None) in ("tool_calls", "function_call")


def _route_footer_chunk(chunk, footer: str) -> ModelResponseStream:
    choices = getattr(chunk, "choices", None)
    index = getattr(choices[0], "index", 0) if choices else 0
    return ModelResponseStream(
        id=getattr(chunk, "id", None),
        created=getattr(chunk, "created", None),
        model=getattr(chunk, "model", None),
        choices=[StreamingChoices(index=index, delta=Delta(content=footer))],
    )


class TraceLogger(CustomLogger):
    def _write(self, kwargs, response_obj, start_time, end_time, status: str):
        try:
            slo = kwargs.get("standard_logging_object") or {}
            usage = _usage(response_obj)
            raw_response = _raw_response(kwargs)
            hints = _hint_headers(slo, kwargs)
            hidden = slo.get("hidden_params") or {}
            provider = slo.get("custom_llm_provider") or (kwargs.get("litellm_params") or {}).get("custom_llm_provider")
            is_ollama = str(provider or "").startswith("ollama")
            rec = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "status": status,
                "requested_model": slo.get("model_group") or kwargs.get("model"),
                "model": slo.get("model") or kwargs.get("model"),
                "provider": provider,
                "process": "ollama" if is_ollama else str(provider or "unknown"),
                "api_base": slo.get("api_base"),
                "call_type": slo.get("call_type") or kwargs.get("call_type"),
                "prompt_tokens": slo.get("prompt_tokens") or usage.get("prompt_tokens") or 0,
                "completion_tokens": slo.get("completion_tokens") or usage.get("completion_tokens") or 0,
                "cost": slo.get("response_cost") or kwargs.get("response_cost") or 0.0,
                "latency_ms": int((end_time - start_time).total_seconds() * 1000) if start_time and end_time else None,
                "model_load_ms": _duration_ms(raw_response.get("load_duration")) if is_ollama else None,
                "input_ms": _duration_ms(raw_response.get("prompt_eval_duration")) if is_ollama else None,
                "inference_ms": _duration_ms(raw_response.get("eval_duration")) if is_ollama else None,
                "model_total_ms": _duration_ms(raw_response.get("total_duration")) if is_ollama else None,
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
            if status == "success":
                _emit_phoenix_metrics(rec)
        except Exception as e:  # noqa: BLE001 - logging must never break the proxy
            print(f"[custom_callbacks] trace write failed: {e}")

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._write(kwargs, response_obj, start_time, end_time, "success")

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        self._write(kwargs, response_obj, start_time, end_time, "failure")

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        footer = _routing_footer(data)
        if footer:
            _append_route_footer(response, footer)
        return response

    async def async_post_call_streaming_iterator_hook(
        self, user_api_key_dict, response, request_data
    ) -> AsyncGenerator[ModelResponseStream, None]:
        footer = _routing_footer(request_data)
        footer_added = False
        tool_call_response = False
        async for chunk in response:
            if _stream_finished_with_tool_call(chunk):
                tool_call_response = True
            if footer and not footer_added and not tool_call_response:
                choices = getattr(chunk, "choices", None)
                if choices and getattr(choices[0], "finish_reason", None):
                    yield _route_footer_chunk(chunk, footer)
                    footer_added = True
            yield chunk
        if footer and not footer_added and not tool_call_response:
            yield _route_footer_chunk(None, footer)


proxy_handler_instance = TraceLogger()
