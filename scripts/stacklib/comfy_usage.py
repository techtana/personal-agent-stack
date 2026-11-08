"""ComfyUI's image jobs as usage records (source comfyui), for the tray's Usage tab.

Open WebUI sends images straight to ComfyUI, so the gateway never sees them. ComfyUI keeps the jobs it ran in memory
(GET /history, up to 10,000, until it restarts). The tray calls `collect` on every poll while ComfyUI answers and writes
one record per finished job it has not recorded yet: model, images, steps and size, model and queue time. A job that
finishes after the last collection and before ComfyUI restarts is not counted; a job whose sampler ComfyUI answered
from its cache ran no model and is not counted either.

Who asked comes from what ComfyUI stored with the job: its own web page marks jobs "comfyui-frontend", stack scripts
send client_id or Comfy-Usage-Source "agent-stack-<id>", and Open WebUI sends a random UUID as client_id.
"""
from __future__ import annotations

import json
import re
import threading
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import traces, usage_log

STATE = "state.json"  # in traces/usage/comfyui: the end time (ms) up to which jobs are recorded
RECENT = 16  # jobs asked for on a routine poll; each one carries its whole workflow
FIRST = 500  # jobs read when nothing was recorded yet, or when more than RECENT finished since the last poll
# (node class, input naming the main model file). The first one found names the job's model.
LOADERS = (("UNETLoader", "unet_name"), ("UnetLoaderGGUF", "unet_name"), ("CheckpointLoaderSimple", "ckpt_name"),
           ("CheckpointLoader", "ckpt_name"), ("ImageOnlyCheckpointLoader", "ckpt_name"))
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_lock = threading.Lock()  # the tray refreshes from its poller and from start/stop threads


def _label(file_name: str) -> str:
    """'z_image_turbo_int8_convrot.safetensors' -> 'Z-Image-Turbo int8' (the chat label's name); else the file stem."""
    from . import media

    for m in media.MODELS:
        if m.name == file_name and m.workflow in media.WORKFLOW_LABELS:
            return media.WORKFLOW_LABELS[m.workflow]
    return Path(file_name).stem or file_name or "?"


def _nodes(graph: dict) -> list[tuple[str, dict]]:
    return [(str(k), n) for k, n in (graph or {}).items() if isinstance(n, dict)]


def model_of(graph: dict) -> str:
    nodes = [n for _, n in _nodes(graph)]
    for cls, key in LOADERS:
        for n in nodes:
            name = (n.get("inputs") or {}).get(key) if isinstance(n.get("inputs"), dict) else None
            if n.get("class_type") == cls and isinstance(name, str) and name:
                return _label(name)
    return "?"


def settings_of(graph: dict) -> dict:
    """Steps and size of a job (KSampler and the empty latent image), when the workflow has them."""
    out: dict = {}
    for _, n in _nodes(graph):
        inputs, cls = n.get("inputs") if isinstance(n.get("inputs"), dict) else {}, str(n.get("class_type") or "")
        if cls.startswith("KSampler") and isinstance(inputs.get("steps"), int):
            out.setdefault("steps", inputs["steps"])
        if cls.startswith("Empty") and "Latent" in cls and isinstance(inputs.get("width"), int):
            out.setdefault("size", f"{inputs['width']}x{inputs.get('height')}")
    return out


def client_of(extra: dict) -> str:
    from .usage import COMPONENTS

    source, cid = str(extra.get("comfy_usage_source") or ""), str(extra.get("client_id") or "")
    if source == "comfyui-frontend" or isinstance(extra.get("extra_pnginfo"), dict):
        return "ComfyUI web UI"
    for tag in (source, cid):
        if tag.startswith("agent-stack-"):
            return COMPONENTS.get(tag[len("agent-stack-"):], tag[len("agent-stack-"):])
    if _UUID.fullmatch(cid.lower()):
        return "Open WebUI"
    return "API client"


def _events(status: dict) -> tuple[dict[str, int], set[str]]:
    """First timestamp (ms) of each status event (execution_start, execution_success, ...) and the cached node ids."""
    times: dict[str, int] = {}
    cached: set[str] = set()
    for item in (status or {}).get("messages") or []:
        if not (isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[1], dict)):
            continue
        ts = item[1].get("timestamp")
        if isinstance(ts, (int, float)) and not isinstance(ts, bool):
            times.setdefault(str(item[0]), int(ts))
        if item[0] == "execution_cached" and isinstance(item[1].get("nodes"), list):
            cached.update(str(n) for n in item[1]["nodes"])
    return times, cached


def _images(outputs: dict) -> int:
    saved = preview = 0
    for out in (outputs or {}).values() if isinstance(outputs, dict) else ():
        images = out.get("images") if isinstance(out, dict) else None
        for im in images if isinstance(images, list) else ():
            if isinstance(im, dict) and im.get("type") == "temp":
                preview += 1
            else:
                saved += 1
    return saved or preview  # a workflow that only previews still made images


def record_for(prompt_id: str, entry: dict) -> tuple[int, dict | None] | None:
    """(end time in ms, usage record) of a finished job; the record is None when the job ran no model (its sampler
    came from ComfyUI's cache). None while the job runs or when ComfyUI kept no timings."""
    status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
    times, cached = _events(status)
    end = times.get("execution_success") or times.get("execution_error") or times.get("execution_interrupted")
    if not end or not (status.get("completed") or status.get("status_str") in ("success", "error")):
        return None
    prompt = entry.get("prompt") if isinstance(entry.get("prompt"), (list, tuple)) else []
    graph = prompt[2] if len(prompt) > 2 and isinstance(prompt[2], dict) else {}
    extra = prompt[3] if len(prompt) > 3 and isinstance(prompt[3], dict) else {}
    samplers = [nid for nid, n in _nodes(graph) if str(n.get("class_type") or "").startswith("KSampler")]
    ok = "execution_success" in times
    if ok and samplers and all(nid in cached for nid in samplers):
        return end, None
    start = times.get("execution_start") or end
    created = extra.get("create_time") if isinstance(extra.get("create_time"), (int, float)) else start
    rec = usage_log.make(
        "comfyui", model_of(graph), "image", client=client_of(extra), status="success" if ok else "failure",
        ts=datetime.fromtimestamp(end / 1000, timezone.utc), latency_ms=max(0, end - created),
        run_ms=max(0, end - start), images=_images(entry.get("outputs")),
        detail={**settings_of(graph), "job": str(prompt_id)[:36]},
        error="" if ok else "interrupted" if "execution_interrupted" in times else "execution error")
    return end, rec


def _state(path: Path) -> int:
    try:
        return int(json.loads(path.read_text(encoding="utf-8")).get("last_end_ms") or 0)
    except (OSError, ValueError, AttributeError, TypeError):
        return 0


def _recorded(folder: Path, everything: bool) -> set[str]:
    """Job ids already recorded: the last three days' files, or every file when the state was lost."""
    if everything:
        files = sorted(folder.glob("*.jsonl"))
    else:
        today = date.today()
        files = [folder / f"{(today - timedelta(days=i)).isoformat()}.jsonl" for i in range(3)]
    return {str((r.get("detail") or {}).get("job")) for r in traces.read_jsonl(files) if isinstance(r.get("detail"), dict)}


def _history(base_url: str, max_items: int, timeout: float) -> dict | None:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/history?max_items={max_items}", timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - refused, timed out, cut short (IncompleteRead) or not JSON: try next poll
        return None
    return data if isinstance(data, dict) else {}


def _finished(history: dict, last: int, seen: set[str]) -> list[tuple[int, str, dict | None]]:
    out = []
    for pid, entry in history.items():
        if str(pid) in seen or not isinstance(entry, dict):
            continue
        try:
            done = record_for(str(pid), entry)
        except Exception:  # noqa: BLE001 - one odd job must not stop the others (or the tray's poll)
            continue
        if done and done[0] >= last:
            out.append((done[0], str(pid), done[1]))
    return out


def collect(base_url: str, timeout: float = 5.0) -> int:
    """Record the jobs ComfyUI finished since the last call; returns how many records were written. Never raises."""
    if not _lock.acquire(blocking=False):
        return 0  # another thread is collecting right now
    try:
        root = usage_log.directory()
        if root is None:
            return 0
        folder = root / "comfyui"
        state = folder / STATE
        last = _state(state)
        seen = _recorded(folder, everything=not last)
        history = _history(base_url, RECENT if last else FIRST, timeout)
        if history is None:
            return 0
        found = _finished(history, last, seen)
        if last and len(history) >= RECENT and len(found) >= len(history):
            # Every one of the newest jobs is new: more finished since the last poll than were asked for.
            history = _history(base_url, FIRST, timeout) or history
            found = _finished(history, last, seen)
        found.sort(key=lambda d: d[0])
        written, mark = 0, last
        for end, _, rec in found:
            if rec is not None:
                if not usage_log.write(rec, root):
                    break  # keep the mark before this job, so it is tried again on the next poll
                written += 1
            mark = max(mark, end)
        if mark > last:
            try:
                folder.mkdir(parents=True, exist_ok=True)
                state.write_text(json.dumps({"last_end_ms": mark}), encoding="utf-8")
            except OSError:
                pass  # the job ids in the records still keep them from being written twice
        return written
    finally:
        _lock.release()
