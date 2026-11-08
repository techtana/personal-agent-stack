"""Usage of every model the stack runs, for the tray's Usage tab and `stack.py usage`.

Two kinds of trace feed it:

    traces/litellm/*.jsonl          one line per gateway request: chat and embeddings, local models and outside APIs
                                    (written by infrastructure/litellm/custom_callbacks.py)
    traces/usage/<source>/*.jsonl   one line per model call outside the gateway: Whisper, ComfyUI images, direct Ollama
                                    calls (written through stacklib/usage_log.py)

Both become one row shape (`from_gateway`, `from_record`), so a table row can be a gateway alias or service, a model,
or a client, and each row is shown in the units of its kind: tokens, seconds of audio, or images.

Adding something that runs a model: send it through the gateway with User-Agent agent-stack-<id> and add the id to
COMPONENTS, or record each call with usage_log.record(<source>, ...) and add the source to SOURCES. A new service goes
into SERVICE_MODELS, and model use the tab cannot see yet into UNCOUNTED. tests/test_tray_coverage.py checks all four.
"""
from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from . import traces

KINDS = ("chat", "embedding", "transcription", "speech", "image", "load")
TEXT = ("chat", "embedding", "load")
AUDIO = ("transcription", "speech")
KIND_WORDS = {
    "chat": ("chat request", "chat requests"), "embedding": ("embedding request", "embedding requests"),
    "transcription": ("transcription", "transcriptions"), "speech": ("speech request", "speech requests"),
    "image": ("image job", "image jobs"), "load": ("model load", "model loads"),
}
LOCATION_NAMES = {"local": "Local", "confidential-cloud": "Confidential VM", "external": "API", "mixed": "Mixed"}


@dataclass(frozen=True)
class Source:
    label: str                 # the tray's name: the "Alias or service" value, and the client when a record names none
    kinds: tuple[str, ...]     # the kinds of model call it records
    where: str                 # the code that records them


# Programs that run models outside the gateway; each writes usage records under traces/usage/<source>/.
SOURCES: dict[str, Source] = {
    "voice-typing": Source("Voice typing", ("transcription",), "scripts/stacklib/dictation/engine.py"),
    "recordings": Source("Recordings", ("transcription",),
                         "scripts/whisper_mcp.py, the local-whisper MCP server Claude Desktop starts"),
    "comfyui": Source("ComfyUI", ("image",), "scripts/stacklib/comfy_usage.py, from ComfyUI's job history"),
    "ollama": Source("Ollama (direct)", ("chat", "load"), "scripts/stacklib/ollama.py: stack.py bench and the warm-up"),
}

# Programs that call the gateway with User-Agent agent-stack-<id> (usage_log.user_agent): id -> client name shown.
COMPONENTS: dict[str, str] = {
    "voice-typing": "Voice typing",
    "refine": "Refine selection",   # the voice typing app's refine button (stacklib/dictation/refine.py)
    "orchestrator": "Orchestrator",
    "retro": "Retrospective",
    "smoke": "Stack scripts",
}

# What each service in machines/_defaults.yaml `services:` does with models, and where the Usage tab counts it
# (None: it runs no model). tests/test_tray_coverage.py fails when a service is missing, so a new one has to say.
SERVICE_MODELS: dict[str, str | None] = {
    "ollama": "runs the local models; counted where they are asked for (gateway traces and usage records)",
    "litellm": "the gateway: one trace line per chat or embedding request, local model or outside API",
    "phoenix": None,
    "orchestrator": "delegates to the departments through the gateway (agent-stack-orchestrator)",
    "open_webui": "chat, titles, tags and document embeddings through the gateway; images through ComfyUI; the chat "
                  "box's microphone through voice typing's Whisper (source voice-typing, client Open WebUI) once "
                  "`stack.py media provision` points it there, else its own Whisper, in UNCOUNTED",
    "comfyui": "image jobs, collected from ComfyUI's history by the tray (source comfyui)",
    "kokoro": "text to speech, in UNCOUNTED until it records its calls",
    "dictation": "Whisper calls (source voice-typing): its own, and Open WebUI's microphone through "
                 "/v1/audio/transcriptions (client Open WebUI); the text clean-up through the gateway "
                 "(agent-stack-voice-typing); refining selected text through the gateway (agent-stack-refine)",
}


def _openwebui_db(profile: dict) -> Path:
    return Path(profile.get("data_dir") or ".") / "open-webui" / "webui.db"


def _openwebui_setting(profile: dict, key: str) -> tuple[bool, str | None]:
    """(database found, value) of one of Open WebUI's config rows, read only; values are JSON ('"ollama"')."""
    db = _openwebui_db(profile)
    if not db.is_file():
        return False, None
    try:
        con = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
        try:
            row = con.execute("select value from config where key = ?", (key,)).fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return True, None
    return True, None if row is None or row[0] is None else str(row[0]).strip('"')


def _openwebui_stt(profile: dict) -> str:
    """Where the microphone in Open WebUI's chat box goes: "own" (engine "", a faster-whisper model inside Open WebUI
    that records nothing), "stack" (voice typing's /v1/audio/transcriptions, counted under source voice-typing),
    "other" (another engine, or an OpenAI-style URL that is not voice typing's), or "" while Open WebUI is off."""
    if (profile.get("services") or {}).get("open_webui") != "native":
        return ""
    _, engine = _openwebui_setting(profile, "audio.stt.engine")
    if engine is None:  # no database yet: its first start takes services.openwebui_stt_env
        return "stack" if (profile.get("services") or {}).get("dictation") == "native" else "own"
    if not engine:
        return "own"
    if engine != "openai":
        return "other"
    _, url = _openwebui_setting(profile, "audio.stt.openai.api_base_url")
    return "stack" if _is_voice_typing(profile, url) else "other"


def _is_voice_typing(profile: dict, url: str | None) -> bool:
    from .dictation import transcription_url

    try:
        ours = transcription_url(profile)
    except (KeyError, TypeError, ValueError):
        return False
    return (url or "").strip().rstrip("/").lower() in (ours, ours.replace("127.0.0.1", "localhost"))


def _openwebui_direct_embeddings(profile: dict) -> bool:
    """Embeddings straight to Ollama: an install from before they went through the gateway (`stack.py media
    provision` moves them), or a profile without an embedding model."""
    if (profile.get("services") or {}).get("open_webui") != "native":
        return False
    found, engine = _openwebui_setting(profile, "rag.embedding_engine")
    if not found:
        return not (profile.get("models") or {}).get("embed")
    return engine == "ollama"


@dataclass(frozen=True)
class Gap:
    service: str
    text: str
    active: Callable[[dict], bool]


# Model use the tab cannot count (yet), shown under the table while it can happen.
UNCOUNTED = (
    Gap("open_webui", "Open WebUI's own speech-to-text: the microphone in its chat box runs Whisper (base) inside "
                      "Open WebUI until `stack.py media provision` sends it to voice typing's Whisper (voice typing "
                      "on)", lambda p: _openwebui_stt(p) == "own"),
    Gap("open_webui", "Open WebUI's speech-to-text through an engine outside the stack (its Admin Settings > Audio); "
                      "`stack.py media provision` sends it to voice typing's Whisper (voice typing on)",
        lambda p: _openwebui_stt(p) == "other"),
    Gap("open_webui", "Open WebUI's document embeddings, which go straight to Ollama until `stack.py media provision` "
                      "sends them through the gateway (then restart Open WebUI)", _openwebui_direct_embeddings),
    Gap("kokoro", "Kokoro text to speech", lambda p: (p.get("services") or {}).get("kokoro") == "native"),
)


def uncounted(profile: dict) -> list[str]:
    out = []
    for gap in UNCOUNTED:
        try:
            if gap.active(profile):
                out.append(gap.text)
        except Exception:  # noqa: BLE001 - a note must never break the tab
            continue
    return out


# ---------------------------------------------------------------- one row shape for both trace kinds

def _day(ts: str) -> str:
    """Local calendar day of a trace timestamp (traces are written in UTC)."""
    try:
        return datetime.fromisoformat(ts).astimezone().date().isoformat()
    except (TypeError, ValueError):
        return (ts or "")[:10]


# User-agent prefixes of the clients that call the gateway, most specific first.
_CLIENTS = (
    ("aiohttp", "Open WebUI"),           # Open WebUI's task and chat calls (its tool env is Python 3.11 + aiohttp)
    ("python-requests", "Open WebUI"),   # Open WebUI's document embeddings (retrieval/utils.py uses requests)
    ("claude-cli", "Claude Code"),
    ("claude-code", "Claude Code"),
    ("openclaw", "OpenClaw"),
    ("node", "OpenClaw"),                # OpenClaw's Node fetch
    ("undici", "OpenClaw"),
    ("openai/", "OpenAI SDK"),
    ("python-httpx", "Orchestrator"),    # orchestrator/jobs.py before it named itself
    ("python-urllib", "Stack scripts"),  # stack.py smoke, bench, warm-up before they named themselves
    ("curl", "curl"),
)


def client_of(row: dict) -> str:
    """Friendly name of the program that sent a gateway request, from its User-Agent header."""
    ua = str(row.get("user_agent") or "").lower()
    if not ua:
        return "Unknown"
    if ua.startswith("agent-stack-"):
        cid = ua[len("agent-stack-"):].split("/", 1)[0].split(" ", 1)[0]
        return COMPONENTS.get(cid, cid or "Unknown")
    for prefix, name in _CLIENTS:
        if prefix in ua:
            return name
    return ua.split("/", 1)[0][:24] or "Unknown"


def model_key(row: dict, group_by: str) -> str:
    """Grouping key of a raw gateway trace line."""
    if group_by == "served":
        served = str(row.get("model") or "?")
        return served.split("/", 1)[1] if "/" in served else served  # ollama_chat/qwen3.5:9b -> qwen3.5:9b
    if group_by == "client":
        return client_of(row)
    return str(row.get("requested_model") or row.get("model") or "?")


def _num(v) -> float:
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        return 0.0
    return f if f == f and f not in (float("inf"), float("-inf")) else 0.0


def _int(v) -> int:
    return int(_num(v))


def _location(value) -> str:
    v = str(value or "").lower()
    if v in ("external", "cloud", "api"):
        return "external"
    return "confidential-cloud" if v == "confidential-cloud" else "local"


def from_gateway(r: dict) -> dict:
    proc = str(r.get("process") or r.get("provider") or "").lower()
    if r.get("data_class") == "external":
        loc = "external"
    elif r.get("location"):
        loc = _location(r["location"])  # onprem -> local
    elif str(r.get("model") or "").startswith(("ollama/", "ollama_chat/")):
        loc = "local"  # served by Ollama, whatever adapter (/v1/messages reports "anthropic") carried the request
    elif proc.startswith("ollama") or proc in ("", "none", "unknown"):
        loc = "local"  # older traces without a location: every deployment was local, failures had no provider
    else:
        loc = "external"
    call = str(r.get("call_type") or "").lower()
    return {
        "ts": str(r.get("ts") or ""), "alias": str(r.get("requested_model") or r.get("model") or "?"),
        "served": model_key(r, "served"), "client": client_of(r), "kind": "embedding" if "embed" in call else "chat",
        "location": loc, "failed": r.get("status") == "failure", "latency_ms": _num(r.get("latency_ms")),
        "load_ms": _num(r.get("model_load_ms")), "input_ms": _num(r.get("input_ms")),
        "run_ms": _num(r.get("inference_ms")), "input_tokens": _int(r.get("prompt_tokens")),
        "output_tokens": _int(r.get("completion_tokens")), "audio_s": 0.0, "images": 0, "cost": _num(r.get("cost")),
    }


def from_record(r: dict) -> dict:
    src = str(r.get("source") or "?")
    label = SOURCES[src].label if src in SOURCES else src
    detail = r.get("detail") if isinstance(r.get("detail"), dict) else {}
    return {
        "ts": str(r.get("ts") or ""), "alias": label, "served": str(r.get("model") or "?"),
        "client": str(r.get("client") or label), "kind": r.get("kind") if r.get("kind") in KINDS else "chat",
        "preview": bool(detail.get("preview")),
        "location": _location(r.get("location")), "failed": r.get("status") == "failure",
        "latency_ms": _num(r.get("latency_ms")), "load_ms": _num(r.get("load_ms")), "input_ms": _num(r.get("input_ms")),
        "run_ms": _num(r.get("run_ms")), "input_tokens": _int(r.get("input_tokens")),
        "output_tokens": _int(r.get("output_tokens")), "audio_s": _num(r.get("audio_s")), "images": _int(r.get("images")),
        "cost": _num(r.get("cost")),
    }


def rows(days: int) -> list[dict]:
    """Every model call of the last `days` local days, gateway and elsewhere, in one shape."""
    return ([from_gateway(r) for r in traces.litellm_rows(days)]
            + [from_record(r) for r in traces.usage_rows(days)])


def _key(row: dict, group_by: str) -> str:
    return row["served"] if group_by == "served" else row["client"] if group_by == "client" else row["alias"]


# ---------------------------------------------------------------- totals per row

def _new() -> dict:
    return {
        "requests": 0, "errors": 0, "kinds": Counter(), "locations": Counter(), "cost": 0.0, "latency_ms": 0.0,
        # text models (chat, embeddings, loads)
        "text": 0, "prompt_tokens": 0, "completion_tokens": 0,
        "out_tokens": 0, "out_ms": 0.0,  # every request with output: end-to-end speed
        "timed": 0, "timed_tokens": 0, "load_ms": 0.0, "input_ms": 0.0, "inference_ms": 0.0, "timed_latency_ms": 0.0,
        "untimed_latency_ms": 0.0,
        # speech (transcription in, speech out)
        "audio": 0, "audio_s": 0.0, "audio_tokens": 0, "audio_run_ms": 0.0, "audio_ms": 0.0, "audio_loads": 0,
        "audio_load_ms": 0.0,
        # images
        "image_jobs": 0, "images": 0, "image_run_ms": 0.0, "image_ms": 0.0,
        # live previews while you speak: they re-read the phrase so far, so they stay out of requests and audio
        "previews": 0, "preview_ms": 0.0,
        "last": "", "via": set(), "daily": defaultdict(lambda: [0, 0, 0.0, 0]),  # day -> requests, tokens, audio s, images
    }


def _add(m: dict, r: dict, day: str, other_key: str) -> None:
    kind, lat = r["kind"], r["latency_ms"]
    if r.get("preview"):
        m["previews"] += 1
        m["preview_ms"] += r["run_ms"] or lat
        m["last"] = max(m["last"], r["ts"])
        m["via"].add(other_key)
        return
    m["requests"] += 1
    m["errors"] += r["failed"]
    m["kinds"][kind] += 1
    m["locations"][r["location"]] += 1
    m["cost"] += r["cost"]
    m["latency_ms"] += lat
    m["last"] = max(m["last"], r["ts"])
    m["via"].add(other_key)
    d = m["daily"][day]
    d[0] += 1
    if kind in AUDIO:
        m["audio"] += 1
        m["audio_s"] += r["audio_s"]
        m["audio_tokens"] += r["output_tokens"] if kind == "transcription" else r["input_tokens"]
        m["audio_run_ms"] += r["run_ms"] or lat
        m["audio_ms"] += lat
        if r["load_ms"]:
            m["audio_loads"] += 1
            m["audio_load_ms"] += r["load_ms"]
        d[2] += r["audio_s"]
        return
    if kind == "image":
        m["image_jobs"] += 1
        m["images"] += r["images"]
        m["image_run_ms"] += r["run_ms"] or lat
        m["image_ms"] += lat
        d[3] += r["images"]
        return
    m["text"] += 1
    pt, ct = r["input_tokens"], r["output_tokens"]
    m["prompt_tokens"] += pt
    m["completion_tokens"] += ct
    d[1] += pt + ct
    if ct and lat:
        m["out_tokens"] += ct
        m["out_ms"] += lat
    if r["run_ms"]:  # the model reported its own timings (Ollama's eval_duration)
        m["timed"] += 1
        m["timed_tokens"] += ct
        m["load_ms"] += r["load_ms"]
        m["input_ms"] += r["input_ms"]
        m["inference_ms"] += r["run_ms"]
        m["timed_latency_ms"] += lat
    else:
        m["untimed_latency_ms"] += lat


def _finish(name: str, m: dict, day_list: list[str]) -> dict:
    n, t, u = m["requests"], m["timed"], m["text"] - m["timed"]
    kinds = m["kinds"]
    locations = set(m["locations"])
    daily = [m["daily"].get(d, [0, 0, 0.0, 0]) for d in day_list]
    audio_s, images = m["audio_s"], m["images"]
    return {
        "model": name,
        # the kind most of its requests were (a row of cancelled dictations has previews only)
        "kind": kinds.most_common(1)[0][0] if kinds else "transcription" if m["previews"] else "chat",
        "kinds": dict(kinds),
        "location": next(iter(locations)) if len(locations) == 1 else "mixed" if locations else "local",
        "requests": n,
        "errors": m["errors"],
        "prompt_tokens": m["prompt_tokens"],
        "completion_tokens": m["completion_tokens"],
        "cost": m["cost"],
        "avg_latency_ms": m["latency_ms"] / n if n else 0,
        # Decode speed: tokens / the model's own generation time, over the requests it timed.
        "decode_tok_s": m["timed_tokens"] / (m["inference_ms"] / 1000) if m["inference_ms"] else None,
        # End-to-end speed: every request's output over its wall-clock time (load, prompt, queue and generation).
        "e2e_tok_s": m["out_tokens"] / (m["out_ms"] / 1000) if m["out_ms"] else None,
        "text_requests": m["text"],
        "timed": t,
        # Average per timed request; "other" is the gateway, network and queue time the model did not report.
        "breakdown_ms": {
            "load": m["load_ms"] / t, "prompt": m["input_ms"] / t, "generate": m["inference_ms"] / t,
            "other": max(0.0, (m["timed_latency_ms"] - m["load_ms"] - m["input_ms"] - m["inference_ms"]) / t),
        } if t else None,
        "untimed_avg_ms": m["untimed_latency_ms"] / u if u else None,
        "audio_requests": m["audio"],
        "audio_s": audio_s,
        "audio_tokens": m["audio_tokens"],
        "audio_run_s": m["audio_run_ms"] / 1000,
        # Seconds of audio per second of model time (realtime factor), and per second on the wall clock.
        "rtf": audio_s / (m["audio_run_ms"] / 1000) if m["audio_run_ms"] and audio_s else None,
        "rtf_wall": audio_s / (m["audio_ms"] / 1000) if m["audio_ms"] and audio_s else None,
        "audio_loads": m["audio_loads"],
        "previews": m["previews"],
        "preview_s": m["preview_ms"] / 1000,
        "audio_load_avg_s": m["audio_load_ms"] / m["audio_loads"] / 1000 if m["audio_loads"] else None,
        "image_jobs": m["image_jobs"],
        "images": images,
        "image_s": m["image_run_ms"] / 1000 / images if images else None,
        "image_wall_s": m["image_ms"] / 1000 / images if images else None,
        "last": m["last"],
        "via": sorted(m["via"]),
        "daily": [d[1] for d in daily],            # tokens per day (text models)
        "daily_requests": [d[0] for d in daily],
        "daily_audio_min": [d[2] / 60 for d in daily],
        "daily_images": [d[3] for d in daily],
    }


def summarize(days: int = 7, group_by: str = "alias") -> dict:
    """Totals, one row per key and per-day series for the last `days` local days (1 = today).

    group_by: "alias" groups by what was asked for: the gateway alias (local-primary, docs, ...) or the service that
    ran the model (Voice typing, ComfyUI, ...); "served" by the model that did the work (qwen3.5:9b, large-v3-turbo,
    claude-haiku-5-5, ...); "client" by the program that asked (Open WebUI, Claude Code, Voice typing, ...).
    Every row also carries "clients": the same figures split by client (by alias when grouped by client).
    """
    # Files are named by local day; read one extra day for timestamps near midnight.
    all_rows = rows(days + 1)
    first = (date.today() - timedelta(days=days - 1)).isoformat()
    sub_by = "alias" if group_by == "client" else "client"
    other_by = "served" if group_by == "alias" else "alias"
    per: dict[str, dict] = defaultdict(_new)
    sub: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(_new))
    total = _new()
    for r in all_rows:
        day = _day(r["ts"])
        if day < first:
            continue
        key, other = _key(r, group_by), _key(r, other_by)
        _add(per[key], r, day, other)
        _add(sub[key][_key(r, sub_by)], r, day, other)
        _add(total, r, day, other)

    day_list = [(date.today() - timedelta(days=i)).isoformat() for i in reversed(range(days))]
    models = []
    for name, m in per.items():
        row = _finish(name, m, day_list)
        row["clients"] = sorted((_finish(c, cm, day_list) for c, cm in sub[name].items()),
                                key=lambda x: (-x["requests"], x["model"]))
        models.append(row)
    models.sort(key=lambda x: (-x["requests"], x["model"]))
    totals = _finish("All", total, day_list)
    return {"days": day_list, "models": models, "totals": totals, "sub_by": sub_by}


# ---------------------------------------------------------------- text for the tab

def compact(n: float) -> str:
    n = float(n)
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(n) >= div:
            v = n / div
            return f"{v:.1f}{suffix}" if v < 100 else f"{v:.0f}{suffix}"
    return f"{n:.0f}"


def duration(seconds: float) -> str:
    """'4.2 s', '35 s', '14.2 min', '2.3 h'."""
    if seconds < 10:
        return f"{seconds:.1f} s"
    if seconds < 60:
        return f"{seconds:.0f} s"
    if seconds < 3600:
        return f"{seconds / 60:.1f} min"
    return f"{seconds / 3600:.1f} h"


def _times(x: float | None) -> str:
    return "-" if not x else f"{x:.1f}x" if x < 10 else f"{x:.0f}x"


def cells(m: dict) -> dict[str, str]:
    """Input, output and the two speeds of a table row, in the units of its main kind. Speed is the model's own pace
    (decode tok/s, audio seconds per second of model time, model seconds per image); overall adds load and queue."""
    k = m["kind"]
    if k in AUDIO:
        audio = duration(m["audio_s"]) if m["audio_s"] else "-"
        toks = f"{compact(m['audio_tokens'])} tok" if m["audio_tokens"] else "-"
        inp, out = (audio, toks) if k == "transcription" else (toks, audio)
        return {"input": inp, "output": out, "speed": _times(m["rtf"]), "overall": _times(m["rtf_wall"])}
    if k == "image":
        return {"input": "-", "output": f"{m['images']:,} img" if m["images"] else "-",
                "speed": f"{m['image_s']:.1f} s/img" if m["image_s"] else "-",
                "overall": f"{m['image_wall_s']:.1f} s/img" if m["image_wall_s"] else "-"}
    return {"input": f"{compact(m['prompt_tokens'])} tok" if m["prompt_tokens"] else "-",
            "output": f"{compact(m['completion_tokens'])} tok" if m["completion_tokens"] else "-",
            "speed": f"{m['decode_tok_s']:.0f} tok/s" if m["decode_tok_s"] else "-",
            "overall": f"{m['e2e_tok_s']:.0f} tok/s" if m["e2e_tok_s"] else "-"}


def sort_value(m: dict, key: str) -> float:
    """Number behind a table column, for sorting rows of mixed kinds."""
    k = m["kind"]
    if key == "input":
        return m["audio_s"] if k == "transcription" else m["prompt_tokens"]
    if key == "output":
        return m["images"] if k == "image" else m["audio_s"] if k == "speech" else (
            m["audio_tokens"] if k == "transcription" else m["completion_tokens"])
    if key in ("speed", "overall"):
        if k in AUDIO:
            v = m["rtf"] if key == "speed" else m["rtf_wall"]
        elif k == "image":
            s = m["image_s"] if key == "speed" else m["image_wall_s"]
            v = 1 / s if s else None
        else:
            v = m["decode_tok_s"] if key == "speed" else m["e2e_tok_s"]
        return v if v is not None else -1
    v = m.get(key)
    return v if isinstance(v, (int, float)) else -1


# Series the chart can show: (title, unit for the hover text, row field).
MEASURES = {
    "requests": ("Requests per day", "requests", "daily_requests"),
    "tokens": ("Tokens per day", "tokens", "daily"),
    "audio": ("Audio minutes per day", "min of audio", "daily_audio_min"),
    "images": ("Images per day", "images", "daily_images"),
}


def measure(m: dict) -> str:
    """The chart series that fits a row: its kind's own unit."""
    k = m["kind"]
    return "audio" if k in AUDIO else "images" if k == "image" else "tokens"


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


def _count(n: int, kind: str) -> str:
    one, many = KIND_WORDS.get(kind, ("request", "requests"))
    return f"{n:,} {one if n == 1 else many}"


def _text_part(m: dict) -> list[str]:
    n, t = m["text_requests"], m["timed"]
    if not n:
        return []
    if set(m.get("kinds") or ()) == {"load"}:  # warm-ups: a load and nothing else
        return [f"{_secs(m['avg_latency_ms'])} each"]
    parts = []
    b = m.get("breakdown_ms")
    if b:
        parts.append(f"{t:,} timed by Ollama, average {_secs(b['load'])} load + {_secs(b['prompt'])} prompt + "
                     f"{_secs(b['generate'])} generate + {_secs(b['other'])} gateway and queue"
                     + (f" ({m['decode_tok_s']:.0f} tok/s while generating)" if m.get("decode_tok_s") else ""))
    if m.get("untimed_avg_ms") is not None:
        parts.append(f"{n - t:,} without Ollama timings, {_secs(m['untimed_avg_ms'])} each on the wall clock, "
                     "queue included")
    if m.get("e2e_tok_s"):
        parts.append(f"Overall {m['e2e_tok_s']:.0f} tok/s")
    return parts


def _audio_part(m: dict) -> list[str]:
    parts = []
    if m["audio_requests"]:
        text = f"{duration(m['audio_s'])} of audio in {duration(m['audio_run_s'])} of model time"
        if m.get("rtf"):
            text += f" ({_times(m['rtf'])} realtime)"
        parts.append(text)
        if m["audio_loads"]:
            parts.append(f"{m['audio_loads']:,} waited for the model to load, {m['audio_load_avg_s']:.1f} s each")
    if m.get("previews"):
        n = m["previews"]
        parts.append(f"Plus {n:,} live preview{'s' if n != 1 else ''} while you spoke, "
                     f"{duration(m['preview_s'])} of model time, not in the totals")
    return parts


def _image_part(m: dict) -> list[str]:
    if not m["image_jobs"]:
        return []
    if not m["images"]:
        return ["no image came out"]
    return [f"{m['images']:,} image{'s' if m['images'] != 1 else ''}, {m['image_s']:.1f} s of model time each, "
            f"{m['image_wall_s']:.1f} s each with the queue"]


def breakdown_text(m: dict, title: str) -> str:
    """One paragraph on what a row's requests were and where their time went."""
    n = m["requests"]
    if not n:
        return f"{title}: no requests." if not m.get("previews") else f"{title}: no finished dictation. " + \
            ". ".join(_audio_part(m)) + "."
    kinds = m.get("kinds") or {m.get("kind", "chat"): n}
    if len(kinds) == 1:
        only = next(iter(kinds))
        head = f"{title}: {n:,} request{'s' if n != 1 else ''}" if only == "chat" else f"{title}: {_count(n, only)}"
    else:
        head = f"{title}: {n:,} requests (" + ", ".join(
            _count(c, k) for k, c in sorted(kinds.items(), key=lambda kv: -kv[1])) + ")"
    if m.get("errors"):
        head += f", {m['errors']:,} failed"
    parts = [head, *_text_part(m), *_audio_part(m), *_image_part(m)]
    if m.get("location") in ("external", "mixed") and m.get("cost"):
        parts.append(f"API cost ${m['cost']:.4f}")
    return ". ".join(parts) + "."
