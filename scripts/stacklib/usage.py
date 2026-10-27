"""Per-model usage from the gateway's JSONL traces (traces/litellm/*.jsonl), for the tray's Usage tab."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from . import traces


def _day(ts: str) -> str:
    """Local calendar day of a trace timestamp (traces are written in UTC)."""
    try:
        return datetime.fromisoformat(ts).astimezone().date().isoformat()
    except (TypeError, ValueError):
        return (ts or "")[:10]


def model_key(row: dict, group_by: str) -> str:
    if group_by == "served":
        served = str(row.get("model") or "?")
        return served.split("/", 1)[1] if "/" in served else served  # ollama_chat/qwen3.5:9b -> qwen3.5:9b
    return str(row.get("requested_model") or row.get("model") or "?")


def summarize(days: int = 7, group_by: str = "alias") -> dict:
    """Totals, one row per model and per-day token counts for the last `days` local days (1 = today).

    group_by: "alias" groups by the gateway model the client asked for (local-primary, docs, ...);
    "served" groups by the model that actually answered (qwen3.5:9b, claude-haiku-5-5, ...).
    """
    # Files are named by UTC day; read one extra so the local-day window is complete.
    rows = traces.litellm_rows(days + 1)
    first = (date.today() - timedelta(days=days - 1)).isoformat()
    per: dict[str, dict] = defaultdict(lambda: {
        "requests": 0, "errors": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0,
        "latency_ms": 0, "gen_tokens": 0, "gen_ms": 0.0, "last": "", "served": set(), "daily": defaultdict(int),
    })
    for r in rows:
        day = _day(r.get("ts") or "")
        if day < first:
            continue
        m = per[model_key(r, group_by)]
        m["requests"] += 1
        m["errors"] += r.get("status") == "failure"
        pt, ct = int(r.get("prompt_tokens") or 0), int(r.get("completion_tokens") or 0)
        m["prompt_tokens"] += pt
        m["completion_tokens"] += ct
        m["cost"] += float(r.get("cost") or 0)
        m["latency_ms"] += int(r.get("latency_ms") or 0)
        # Decode speed: Ollama's own inference time when the callback recorded it, else wall-clock latency.
        gen_ms = r.get("inference_ms") or r.get("latency_ms")
        if ct and gen_ms:
            m["gen_tokens"] += ct
            m["gen_ms"] += float(gen_ms)
        m["last"] = max(m["last"], r.get("ts") or "")
        m["served"].add(model_key(r, "served" if group_by == "alias" else "alias"))
        m["daily"][day] += pt + ct

    day_list = [(date.today() - timedelta(days=i)).isoformat() for i in reversed(range(days))]
    models = []
    for name, m in per.items():
        n = m["requests"]
        models.append({
            "model": name,
            "requests": n,
            "errors": m["errors"],
            "prompt_tokens": m["prompt_tokens"],
            "completion_tokens": m["completion_tokens"],
            "cost": m["cost"],
            "avg_latency_ms": m["latency_ms"] / n if n else 0,
            "tok_per_s": m["gen_tokens"] / (m["gen_ms"] / 1000) if m["gen_ms"] else None,
            "last": m["last"],
            "via": sorted(m["served"]),
            "daily": [m["daily"].get(d, 0) for d in day_list],
        })
    models.sort(key=lambda x: (-(x["prompt_tokens"] + x["completion_tokens"]), x["model"]))
    totals = {k: sum(x[k] for x in models) for k in ("requests", "errors", "prompt_tokens", "completion_tokens", "cost")}
    totals["daily"] = [sum(x["daily"][i] for x in models) for i in range(len(day_list))]
    return {"days": day_list, "models": models, "totals": totals}


def ago(ts: str) -> str:
    """'3 min ago' style label for a trace timestamp."""
    try:
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return "-"
    s = int(delta.total_seconds())
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{s // 60} min ago"
    if s < 86400:
        return f"{s // 3600} h ago"
    return f"{s // 86400} d ago"
