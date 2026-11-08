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


# User-agent prefixes of the clients that call the gateway, most specific first.
_CLIENTS = (
    ("aiohttp", "Open WebUI"),           # Open WebUI's task and chat calls (its tool env is Python 3.11 + aiohttp)
    ("claude-cli", "Claude Code"),
    ("claude-code", "Claude Code"),
    ("openclaw", "OpenClaw"),
    ("node", "OpenClaw"),                # OpenClaw's Node fetch
    ("undici", "OpenClaw"),
    ("openai/", "OpenAI SDK"),
    ("python-httpx", "Orchestrator"),    # orchestrator/jobs.py
    ("agent-stack-voice-typing", "Voice typing"),   # dictation cleanup (scripts/stacklib/dictation/cleanup.py)
    ("agent-stack-refine", "Refine selection"),     # the refine button (scripts/stacklib/dictation/refine.py)
    ("python-urllib", "Stack scripts"),  # stack.py smoke, bench, warm-up
    ("curl", "curl"),
)


def client_of(row: dict) -> str:
    """Friendly name of the program that sent a request, from its User-Agent header."""
    ua = str(row.get("user_agent") or "").lower()
    if not ua:
        return "Unknown"
    for prefix, name in _CLIENTS:
        if prefix in ua:
            return name
    return ua.split("/", 1)[0][:24] or "Unknown"


def model_key(row: dict, group_by: str) -> str:
    if group_by == "served":
        served = str(row.get("model") or "?")
        return served.split("/", 1)[1] if "/" in served else served  # ollama_chat/qwen3.5:9b -> qwen3.5:9b
    if group_by == "client":
        return client_of(row)
    return str(row.get("requested_model") or row.get("model") or "?")


def _new() -> dict:
    return {
        "requests": 0, "errors": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0, "latency_ms": 0,
        "out_tokens": 0, "out_ms": 0.0,  # every request with output: end-to-end speed
        "timed": 0, "timed_tokens": 0, "load_ms": 0.0, "input_ms": 0.0, "inference_ms": 0.0, "timed_latency_ms": 0.0,
        "untimed_latency_ms": 0.0, "last": "", "served": set(), "daily": defaultdict(int),
    }


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _add(m: dict, r: dict, day: str, other_key: str) -> None:
    m["requests"] += 1
    m["errors"] += r.get("status") == "failure"
    pt, ct = int(r.get("prompt_tokens") or 0), int(r.get("completion_tokens") or 0)
    lat = _num(r.get("latency_ms"))
    m["prompt_tokens"] += pt
    m["completion_tokens"] += ct
    m["cost"] += _num(r.get("cost"))
    m["latency_ms"] += lat
    if ct and lat:
        m["out_tokens"] += ct
        m["out_ms"] += lat
    inf = _num(r.get("inference_ms"))
    if inf:  # Ollama reported its own timings for this request
        m["timed"] += 1
        m["timed_tokens"] += ct
        m["load_ms"] += _num(r.get("model_load_ms"))
        m["input_ms"] += _num(r.get("input_ms"))
        m["inference_ms"] += inf
        m["timed_latency_ms"] += lat
    else:
        m["untimed_latency_ms"] += lat
    m["last"] = max(m["last"], r.get("ts") or "")
    m["served"].add(other_key)
    m["daily"][day] += pt + ct


def _finish(name: str, m: dict, day_list: list[str]) -> dict:
    n, t = m["requests"], m["timed"]
    u = n - t
    return {
        "model": name,
        "requests": n,
        "errors": m["errors"],
        "prompt_tokens": m["prompt_tokens"],
        "completion_tokens": m["completion_tokens"],
        "cost": m["cost"],
        "avg_latency_ms": m["latency_ms"] / n if n else 0,
        # Decode speed: tokens / Ollama's own generation time, over the requests Ollama timed.
        "decode_tok_s": m["timed_tokens"] / (m["inference_ms"] / 1000) if m["inference_ms"] else None,
        # End-to-end speed: every request's output over its wall-clock time (load, prompt, queue and generation).
        "e2e_tok_s": m["out_tokens"] / (m["out_ms"] / 1000) if m["out_ms"] else None,
        "timed": t,
        # Average per timed request; "other" is the gateway, network and queue time Ollama did not report.
        "breakdown_ms": {
            "load": m["load_ms"] / t, "prompt": m["input_ms"] / t, "generate": m["inference_ms"] / t,
            "other": max(0.0, (m["timed_latency_ms"] - m["load_ms"] - m["input_ms"] - m["inference_ms"]) / t),
        } if t else None,
        "untimed_avg_ms": m["untimed_latency_ms"] / u if u else None,
        "last": m["last"],
        "via": sorted(m["served"]),
        "daily": [m["daily"].get(d, 0) for d in day_list],
    }


def summarize(days: int = 7, group_by: str = "alias") -> dict:
    """Totals, one row per model and per-day token counts for the last `days` local days (1 = today).

    group_by: "alias" groups by the gateway model the client asked for (local-primary, docs, ...);
    "served" groups by the model that actually answered (qwen3.5:9b, claude-haiku-5-5, ...);
    "client" groups by the program that sent the request (Open WebUI, Claude Code, OpenClaw, ...).
    Every row also carries "clients": the same figures split by client (by alias when grouped by client).
    """
    # Files are named by UTC day; read one extra so the local-day window is complete.
    rows = traces.litellm_rows(days + 1)
    first = (date.today() - timedelta(days=days - 1)).isoformat()
    sub_by = "alias" if group_by == "client" else "client"
    other_by = "served" if group_by == "alias" else "alias"
    per: dict[str, dict] = defaultdict(_new)
    sub: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(_new))
    total = _new()
    for r in rows:
        day = _day(r.get("ts") or "")
        if day < first:
            continue
        key, other = model_key(r, group_by), model_key(r, other_by)
        _add(per[key], r, day, other)
        _add(sub[key][model_key(r, sub_by)], r, day, other)
        _add(total, r, day, other)

    day_list = [(date.today() - timedelta(days=i)).isoformat() for i in reversed(range(days))]
    models = []
    for name, m in per.items():
        row = _finish(name, m, day_list)
        row["clients"] = sorted((_finish(c, cm, day_list) for c, cm in sub[name].items()),
                                key=lambda x: (-x["requests"], x["model"]))
        models.append(row)
    models.sort(key=lambda x: (-(x["prompt_tokens"] + x["completion_tokens"]), x["model"]))
    totals = _finish("All", total, day_list)
    return {"days": day_list, "models": models, "totals": totals, "sub_by": sub_by}


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


def _secs(ms: float) -> str:
    return f"{ms / 1000:.1f} s"


def breakdown_text(m: dict, title: str) -> str:
    """One paragraph on where a row's time went: Ollama's own timings, the rest, and requests Ollama did not time."""
    n, t = m["requests"], m["timed"]
    if not n:
        return f"{title}: no requests."
    parts = [f"{title}: {n:,} request{'s' if n != 1 else ''}"]
    b = m.get("breakdown_ms")
    if b:
        parts.append(f"{t:,} timed by Ollama, average {_secs(b['load'])} load + {_secs(b['prompt'])} prompt + "
                     f"{_secs(b['generate'])} generate + {_secs(b['other'])} gateway and queue"
                     + (f" ({m['decode_tok_s']:.0f} tok/s while generating)" if m.get("decode_tok_s") else ""))
    if m.get("untimed_avg_ms") is not None:
        u = n - t
        parts.append(f"{u:,} without Ollama timings, {_secs(m['untimed_avg_ms'])} each on the wall clock, queue included")
    if m.get("e2e_tok_s"):
        parts.append(f"Overall {m['e2e_tok_s']:.0f} tok/s")
    return ". ".join(parts) + "."
