"""Aggregate local LiteLLM request traces for the tray metrics table."""
from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

PERIODS = {
    "1 hour": timedelta(hours=1),
    "24 hours": timedelta(hours=24),
    "7 days": timedelta(days=7),
    "30 days": timedelta(days=30),
    "All time": None,
}

_AVERAGE_FIELDS = ("model_load_ms", "input_ms", "inference_ms", "model_total_ms", "latency_ms")


def _timestamp(value: str) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _number(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return 0.0
    return float(value)


def _process(record: dict) -> str:
    process = record.get("process")
    if process:
        return str(process)
    provider = str(record.get("provider") or "unknown")
    return "ollama" if provider.startswith("ollama") else provider


def _model(record: dict) -> str:
    model = str(record.get("model") or record.get("requested_model") or "unknown")
    for prefix in ("ollama_chat/", "ollama/", "anthropic/"):
        if model.startswith(prefix):
            return model[len(prefix):]
    return model


def summarize(directory: Path, period: str, now: datetime | None = None) -> list[dict]:
    """Return request/token/cost totals and mean operation durations grouped by process and model."""
    if period not in PERIODS:
        raise ValueError(f"unsupported metrics period: {period}")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    duration = PERIODS[period]
    cutoff = current - duration if duration is not None else None
    groups: dict[tuple[str, str], dict] = {}

    for path in sorted(directory.glob("*.jsonl")):
        with path.open(encoding="utf-8") as trace_file:
            for line in trace_file:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                timestamp = _timestamp(record.get("ts"))
                if timestamp is None or (cutoff is not None and timestamp < cutoff):
                    continue
                process, model = _process(record), _model(record)
                group = groups.setdefault(
                    (process, model),
                    {
                        "process": process,
                        "model": model,
                        "requests": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "cost_usd": 0.0,
                        **{f"_{field}": [] for field in _AVERAGE_FIELDS},
                    },
                )
                group["requests"] += 1
                group["prompt_tokens"] += int(_number(record.get("prompt_tokens")))
                group["completion_tokens"] += int(_number(record.get("completion_tokens")))
                group["cost_usd"] += _number(record.get("cost"))
                for field in _AVERAGE_FIELDS:
                    value = record.get(field)
                    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
                        group[f"_{field}"].append(float(value))

    rows = []
    for group in groups.values():
        row = {key: value for key, value in group.items() if not key.startswith("_")}
        for field in _AVERAGE_FIELDS:
            values = group[f"_{field}"]
            row[f"avg_{field}"] = statistics.fmean(values) if values else None
        rows.append(row)
    return sorted(rows, key=lambda row: (row["process"], row["model"].casefold()))
