"""Usage records for model calls that do not pass through the gateway, for the tray's Usage tab.

The gateway writes one line per request itself (infrastructure/litellm/custom_callbacks.py, traces/litellm/). Every
other program that runs a model writes one line per call through `record`: Whisper in voice typing, ComfyUI images
(collected from its history by the tray), direct Ollama calls from stack scripts. The recordings MCP server
(scripts/whisper_mcp.py) runs from a copy outside the repository and writes the same format with its own few lines.

    traces/usage/<source>/<local date>.jsonl     one folder per source, so two programs never append to one file

Fields (no prompt, transcript, image or document content, ever):

    ts             UTC time the call finished, ISO 8601 seconds
    source         the component that ran the model; stacklib/usage.py SOURCES names each one for the tray
    client         who asked, as the tray shows it: Voice typing, Claude Desktop, Open WebUI, Stack scripts, ...
    model          the model as the owner knows it: large-v3-turbo, z_image_turbo_int8_convrot, qwen3.5:9b
    kind           chat | embedding | transcription | speech | image | load
    location       local (this machine) | confidential-cloud | external (an outside API: data leaves, may cost)
    status         success | failure
    latency_ms     wall clock of the call: waiting, loading and running
    load_ms        the part spent loading the model, when known
    input_ms       the part spent reading the input (prompt prefill), when known
    run_ms         the part the model worked (decode, diffusion steps), when known
    input_tokens, output_tokens, audio_s, images, cost (USD; 0 for local models)
    detail         a few small settings, such as device, language, steps or size

Standard library only: the voice typing and Whisper environments import it as well. The tray and stack.py call
`configure(profile)`; services they start get the folder through AGENT_STACK_USAGE_DIR, which is "off" when
observability.jsonl_traces is off. Services that started before the switch was turned off (voice typing, the
recordings server Claude Desktop starts) see the RECORDING_OFF file that `sync_switch` leaves in the folder.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ENV = "AGENT_STACK_USAGE_DIR"
OFF = ("", "off", "0", "false", "no")
MARKER = "RECORDING_OFF"  # in the usage folder while observability.jsonl_traces is off
KINDS = ("chat", "embedding", "transcription", "speech", "image", "load")
LOCATIONS = ("local", "confidential-cloud", "external")
_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
# File paths never go into a record: a quoted path whole (spaces and all), then bare Windows drive and UNC paths
# and absolute POSIX paths with two or more parts. A drive letter must not follow a letter (http://, file://).
_QUOTED_PATH = re.compile(r"""(['"])(?:[A-Za-z]:[\\/]|\\\\|/)[^'"]*\1""")
_PATH = re.compile(r"(?<!\w)[A-Za-z]:[\\/][^\s'\"<>|]*|\\\\[^\s'\"<>|]+|(?<![\w.:/])/(?:[^\s'\"/<>|]+/)+[^\s'\"<>|]*")

_lock = threading.Lock()
_configured: list = []      # [Path | None] once configure() ran in this process
_warned: set[str] = set()


def default_dir() -> Path:
    """traces/usage of the checkout this file belongs to."""
    return Path(__file__).resolve().parents[2] / "traces" / "usage"


def dir_for(profile: dict) -> Path | None:
    """Where this profile wants usage records, or None when usage traces are off."""
    return default_dir() if (profile.get("observability") or {}).get("jsonl_traces", True) else None


def env_for(profile: dict) -> dict[str, str]:
    """The environment a service needs to record its model calls (or to know it must not)."""
    d = dir_for(profile)
    return {ENV: str(d) if d else "off"}


def configure(profile: dict) -> None:
    """Follow the profile's switch in this process (the tray, stack.py), whatever the environment says."""
    _configured[:] = [dir_for(profile)]


def sync_switch(profile: dict, folder: Path | None = None) -> None:
    """Leave RECORDING_OFF in the usage folder while the profile's usage traces are off, and remove it when they are
    on, so programs started with the old setting follow the new one. The tray and `stack.py up` call this."""
    marker = (folder or default_dir()) / MARKER
    try:
        if dir_for(profile) is None:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("Usage traces are off (observability.jsonl_traces); nothing records model calls here.\n",
                              encoding="utf-8")
        elif marker.exists():
            marker.unlink()
    except OSError as e:
        print(f"[usage] could not update {marker}: {e}", file=sys.stderr, flush=True)


def directory() -> Path | None:
    if _configured:
        return _configured[0]
    env = os.environ.get(ENV)
    if env is not None:
        d = None if env.strip().lower() in OFF else Path(env)
    else:
        d = default_dir()
    return None if d is None or (d / MARKER).exists() else d


def scrub(text: str) -> str:
    """An error message without file paths (a recording's name, a user folder): '<path>' stands in for each."""
    text = _QUOTED_PATH.sub(lambda m: f"{m.group(1)}<path>{m.group(1)}", str(text or ""))
    return _PATH.sub("<path>", text)


def user_agent(component: str) -> str:
    """User-Agent for a component's own gateway calls, so the Usage tab names it (stacklib/usage.py COMPONENTS)."""
    return f"agent-stack-{component}"


def _round(v):
    return round(v, 3) if isinstance(v, float) else v


def _ms(v) -> float | None:
    """A duration in ms, or None when it is not a finite number of at least 0 (a missing timing, a test double)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")) or v < 0:
        return None
    return float(v)


def _n(v, cast=float):
    """A count or amount; anything that is not a finite number counts as 0."""
    return cast(v) if _ms(v) is not None else cast(0)


def make(source: str, model: str, kind: str, *, client: str = "", status: str = "success", ts: datetime | None = None,
         latency_ms: float | None = None, load_ms: float | None = None, input_ms: float | None = None,
         run_ms: float | None = None, input_tokens: int = 0, output_tokens: int = 0, audio_s: float = 0.0,
         images: int = 0, cost: float = 0.0, location: str = "local", detail: dict | None = None,
         error: str = "") -> dict:
    """One record, checked. Unknown source ids, kinds or locations are programming errors and raise ValueError."""
    if not _ID.fullmatch(source or ""):
        raise ValueError(f"usage source must be a short lower-case id, not {source!r}")
    if kind not in KINDS:
        raise ValueError(f"usage kind must be one of {KINDS}, not {kind!r}")
    if location not in LOCATIONS:
        raise ValueError(f"usage location must be one of {LOCATIONS}, not {location!r}")
    when = (ts or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rec = {"ts": when.isoformat(timespec="seconds"), "source": source, "client": client, "model": model or "?",
           "kind": kind, "location": location, "status": "failure" if status == "failure" else "success",
           "latency_ms": _ms(latency_ms), "load_ms": _ms(load_ms), "input_ms": _ms(input_ms), "run_ms": _ms(run_ms),
           "input_tokens": _n(input_tokens, int), "output_tokens": _n(output_tokens, int),
           "audio_s": _n(audio_s), "images": _n(images, int), "cost": _n(cost),
           "detail": detail or None, "error": scrub(error)[:200] or None}
    return {k: _round(v) for k, v in rec.items() if v is not None and v != ""}


def path_for(directory_: Path, rec: dict) -> Path:
    """File of a record: its source's folder, named by the local day it finished (as the gateway names its files)."""
    day = datetime.fromisoformat(rec["ts"]).astimezone().date().isoformat()
    return directory_ / rec["source"] / f"{day}.jsonl"


def write(rec: dict, directory_: Path | None = None) -> bool:
    """Append a record. Never raises for I/O: usage records must not break the program that runs the model."""
    d = directory_ if directory_ is not None else directory()
    if d is None:
        return False
    try:
        line = json.dumps(rec, ensure_ascii=False, separators=(",", ":"), default=str) + "\n"
        p = path_for(d, rec)
        with _lock:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a", encoding="utf-8") as f:
                f.write(line)
        return True
    except (OSError, ValueError, TypeError, KeyError) as e:
        if rec.get("source") not in _warned:
            _warned.add(rec.get("source", ""))
            print(f"[usage] could not write a usage record for {rec.get('source')}: {e}", file=sys.stderr, flush=True)
        return False


def record(source: str, model: str, kind: str, **fields) -> dict:
    """Record one model call (see make() for the fields) and return the record, written or not."""
    rec = make(source, model, kind, **fields)
    write(rec)
    return rec
