"""Local Whisper transcription as an MCP server (stdio), for Claude Desktop / Cowork and Claude Code.

The audio never leaves this machine: faster-whisper runs on the local GPU (CPU fallback) and only the transcript text
goes back to the MCP client. Note that a cloud client such as Cowork then sends that text to its own model.

`stack.py whisper install` copies this file next to its venv (media.whisper_dir) and registers it in Claude Desktop's
config, so it does not depend on a git checkout. Settings come from environment variables written there:

  WHISPER_ROOTS        folders (os.pathsep-separated) whose recordings may be read; nothing outside them is opened
  WHISPER_RECORDINGS   default folder for list_recordings
  WHISPER_TRANSCRIPTS  where transcripts (.md, .srt, .json) are written and cached
  WHISPER_MODEL        GPU model (default large-v3-turbo); WHISPER_COMPUTE (default int8_float16)
  WHISPER_CPU_MODEL    model when CUDA is unavailable (default small, int8)
  WHISPER_IDLE_UNLOAD  seconds before the model leaves VRAM (default 600)
  HF_HOME              Hugging Face cache for the model download
  AGENT_STACK_USAGE_DIR  the stack checkout's traces/usage folder: one usage record per transcription for the tray's
                       Usage tab (model, audio length, times, tokens; never paths or text). Unset or "off": none.
  AGENT_STACK_CLIENT   the client those records name (Claude Desktop)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ctranslate2 loads cuBLAS 12 and cuDNN 9 with LoadLibrary, which searches PATH; the nvidia-* wheels put them here.
_NV = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
if _NV.is_dir():
    os.environ["PATH"] = os.pathsep.join([*(str(p) for p in _NV.glob("*/bin")), os.environ.get("PATH", "")])
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from fastmcp import FastMCP  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".webm", ".mp4", ".mkv", ".mov", ".avi", ".amr", ".3gp"}
ROOTS = [r for r in os.environ.get("WHISPER_ROOTS", "").split(os.pathsep) if r.strip()]
RECORDINGS = os.environ.get("WHISPER_RECORDINGS", "")
TRANSCRIPTS = Path(os.environ.get("WHISPER_TRANSCRIPTS") or Path(__file__).with_name("transcripts"))
GPU_MODEL = os.environ.get("WHISPER_MODEL", "large-v3-turbo")
GPU_COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8_float16")
CPU_MODEL = os.environ.get("WHISPER_CPU_MODEL", "small")
IDLE_UNLOAD = float(os.environ.get("WHISPER_IDLE_UNLOAD", "600"))
WAIT_MAX = float(os.environ.get("WHISPER_WAIT", "50"))      # seconds a tool call blocks before handing back a job id (client tool calls time out)
PAGE = 40_000       # characters of transcript per reply
USAGE_DIR = os.environ.get("AGENT_STACK_USAGE_DIR", "")
USAGE_CLIENT = os.environ.get("AGENT_STACK_CLIENT") or "MCP client"


# ---------------------------------------------------------------- usage records (the tray's Usage tab)

def record_usage(model: str, device: str, audio_s: float, latency_s: float, load_s: float, run_s: float, tokens: int,
                 language: str, failed: str = "") -> None:
    """One line per transcription in stacklib/usage_log.py's format, which this copy cannot import (it runs outside
    the repository under `python -I`). Never raises: a usage record must not fail a transcription."""
    if USAGE_DIR.strip().lower() in ("", "off", "0", "false", "no"):
        return
    try:
        root = Path(USAGE_DIR)
        if not root.parent.is_dir():  # the checkout moved: do not create folders somewhere else
            return
        if (root / "RECORDING_OFF").exists():  # usage traces were turned off after this server started
            return
        now = datetime.now(timezone.utc)
        rec = {"ts": now.isoformat(timespec="seconds"), "source": "recordings", "client": USAGE_CLIENT,
               "model": model, "kind": "transcription", "location": "local",
               "status": "failure" if failed else "success", "latency_ms": round(latency_s * 1000, 3),
               "run_ms": round(run_s * 1000, 3), "input_tokens": 0, "output_tokens": int(tokens),
               "audio_s": round(float(audio_s), 3), "images": 0, "cost": 0.0}
        if load_s:
            rec["load_ms"] = round(load_s * 1000, 3)
        detail = {k: v for k, v in (("device", device), ("language", language)) if v}
        if detail:
            rec["detail"] = detail
        if failed:
            rec["error"] = failed[:200]
        folder = root / "recordings"
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / f"{now.astimezone().date().isoformat()}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"[whisper] usage record failed: {e}", file=sys.stderr)


# ---------------------------------------------------------------- path guard (decision D-M6)

def _norm(path: str) -> str:
    p = Path(os.path.expandvars(os.path.expanduser(path)))
    try:
        p = p.resolve(strict=False)
    except OSError:
        p = Path(os.path.abspath(p))
    text = os.path.normpath(str(p))
    return text.lower() if os.name == "nt" else text


def allowed(path: str) -> bool:
    if not path or not Path(os.path.expanduser(path)).is_absolute():
        return False
    target = _norm(path)
    return any(target == _norm(r) or target.startswith(_norm(r).rstrip("\\/") + os.sep) for r in ROOTS)


def _refuse(path: str) -> dict:
    return {"error": f"{path} is outside the folders this server may read: {ROOTS or 'none configured'}. "
                     "Move the recording into one of them, or add its folder to agent_access.allowed_roots in "
                     "machines/<HOST>.yaml and rerun `stack.py whisper install`."}


# ---------------------------------------------------------------- model

class Engine:
    def __init__(self) -> None:
        self.model = None
        self.desc = ""
        self.name = ""                   # model name and device of the loaded model, for usage records
        self.device = ""
        self.lock = threading.Lock()     # one transcription at a time; the GPU is shared with Ollama and ComfyUI
        self.last_used = time.time()
        threading.Thread(target=self._reaper, daemon=True).start()

    def _load(self):
        from faster_whisper import WhisperModel
        if self.model is not None:
            return self.model
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() < 1:
                raise RuntimeError("no CUDA device")
            self.model = WhisperModel(GPU_MODEL, device="cuda", compute_type=GPU_COMPUTE)
            self.desc = f"{GPU_MODEL} (cuda, {GPU_COMPUTE})"
            self.name, self.device = GPU_MODEL, "cuda"
        except Exception as e:  # noqa: BLE001 - any CUDA/DLL failure falls back to the CPU
            print(f"[whisper] GPU load failed ({e}); using {CPU_MODEL} on the CPU", file=sys.stderr)
            self.model = WhisperModel(CPU_MODEL, device="cpu", compute_type="int8")
            self.desc = f"{CPU_MODEL} (cpu, int8)"
            self.name, self.device = CPU_MODEL, "cpu"
        return self.model

    def _reaper(self) -> None:
        while True:
            time.sleep(30)
            if self.model is not None and time.time() - self.last_used > IDLE_UNLOAD and self.lock.acquire(blocking=False):
                try:
                    self.model = None
                    print("[whisper] idle: model unloaded", file=sys.stderr)
                finally:
                    self.lock.release()

    def transcribe(self, path: str, language: str | None, prompt: str | None, job: dict) -> dict:
        with self.lock:
            start = time.time()
            loaded = self.model is not None
            info, tokens, load_s, failed = None, 0, 0.0, ""
            t0 = start
            try:
                model = self._load()
                load_s = 0.0 if loaded else time.time() - start
                job["model"] = self.desc
                t0 = time.time()
                segments, info = model.transcribe(path, language=language or None, initial_prompt=prompt or None,
                                                  vad_filter=True, beam_size=5)
                job["duration_s"] = round(info.duration, 1)
                out = []
                for s in segments:
                    tokens += len(getattr(s, "tokens", None) or ())
                    out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
                    job["progress"] = round(min(1.0, s.end / info.duration), 3) if info.duration else None
                self.last_used = time.time()
                return {"language": info.language, "language_probability": round(info.language_probability, 3),
                        "duration_s": round(info.duration, 1), "elapsed_s": round(time.time() - t0, 1),
                        "model": self.desc, "segments": out}
            except Exception as e:
                failed = type(e).__name__  # not the message: decoders put the recording's path in it
                raise
            finally:
                record_usage(self.name or GPU_MODEL, self.device, getattr(info, "duration", 0) or 0,
                             time.time() - start, load_s, time.time() - t0, tokens, getattr(info, "language", "") or "",
                             failed)


ENGINE = Engine()
JOBS: dict[str, dict] = {}


# ---------------------------------------------------------------- transcripts on disk

def _stamp(t: float) -> str:
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def as_text(result: dict) -> str:
    return "\n".join(f"[{_stamp(s['start'])}] {s['text']}" for s in result["segments"])


def cache_key(path: str, language: str | None, prompt: str | None) -> str:
    st = os.stat(path)
    raw = f"{_norm(path)}|{st.st_size}|{int(st.st_mtime)}|{GPU_MODEL}|{language or ''}|{prompt or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()[:10]


def out_base(path: str, key: str) -> Path:
    return TRANSCRIPTS / f"{Path(path).stem}.{key}"


def _f(base: Path, ext: str) -> Path:
    """base + extension; not with_suffix, which would replace the cache key after the stem."""
    return base.with_name(base.name + ext)


def write_outputs(path: str, base: Path, result: dict) -> dict:
    base.parent.mkdir(parents=True, exist_ok=True)
    meta = {k: v for k, v in result.items() if k != "segments"}
    _f(base, ".json").write_text(json.dumps({"source": path, **result}, ensure_ascii=False, indent=1), encoding="utf-8")
    header = (f"# Transcript: {Path(path).name}\n\nSource: {path}  \nLanguage: {meta['language']}  \n"
              f"Duration: {_stamp(meta['duration_s'])}  \nModel: {meta['model']} (local)\n\n")
    _f(base, ".md").write_text(header + as_text(result) + "\n", encoding="utf-8")
    srt = "\n".join(f"{i}\n{_srt_time(s['start'])} --> {_srt_time(s['end'])}\n{s['text']}\n"
                    for i, s in enumerate(result["segments"], 1))
    _f(base, ".srt").write_text(srt, encoding="utf-8")
    return {"markdown": str(_f(base, ".md")), "srt": str(_f(base, ".srt")), "json": str(_f(base, ".json"))}


def reply(job: dict, offset: int = 0) -> dict:
    out = {k: v for k, v in job.items() if k not in ("result", "thread")}
    if job["status"] == "done":
        text = as_text(job["result"])
        chunk = text[offset:offset + PAGE]
        out.update({"language": job["result"]["language"], "segments": len(job["result"]["segments"]),
                    "transcript": chunk, "offset": offset, "total_chars": len(text)})
        if offset + PAGE < len(text):
            out["next_offset"] = offset + PAGE
            out["note"] = f"Transcript continues: call get_transcription(job_id, offset={offset + PAGE})."
    return out


def _run(job: dict, path: str, language: str | None, prompt: str | None, base: Path) -> None:
    job["status"] = "running"
    try:
        result = ENGINE.transcribe(path, language, prompt, job)
        job["files"] = write_outputs(path, base, result)
        job["result"] = result
        job["elapsed_s"] = result["elapsed_s"]
        job["progress"] = 1.0
        job["status"] = "done"
    except Exception as e:  # noqa: BLE001 - reported to the client
        job["status"] = "failed"
        job["error"] = f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- MCP tools

mcp = FastMCP(
    name="local-whisper",
    instructions=(
        "Transcribe audio or video recordings on the owner's own GPU with Whisper; the audio stays on this machine. "
        "Use list_recordings to find files, transcribe_recording to get a timestamped transcript, then analyse the "
        "text (summary, decisions, action items, speakers' topics). Long recordings return a job_id: poll "
        "get_transcription until status is done. Pass language (e.g. 'en', 'th') when known, and put names or jargon "
        "in prompt to improve spelling. Speakers are not separated (no diarisation)."
    ),
)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True))
def list_recordings(folder: str = "", limit: int = 100) -> dict:
    """List audio/video files (newest first) in a folder this server may read; default is the recordings folder.
    Each entry says whether a cached transcript exists."""
    folder = folder or RECORDINGS
    if not allowed(folder):
        return _refuse(folder)
    root = Path(folder)
    if not root.is_dir():
        return {"folder": folder, "recordings": [], "note": "folder does not exist yet"}
    files = sorted((p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXT),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:max(1, min(limit, 500))]
    out = []
    for p in files:
        st = p.stat()
        cached = _f(out_base(str(p), cache_key(str(p), None, None)), ".json").exists()
        out.append({"path": str(p), "size_mb": round(st.st_size / 1e6, 1),
                    "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)), "transcribed": cached})
    return {"folder": folder, "roots": ROOTS, "recordings": out}


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False))
def transcribe_recording(path: str, language: str = "", prompt: str = "", force: bool = False) -> dict:
    """Transcribe one recording locally with Whisper and return the timestamped transcript.
    language: ISO code such as 'en' or 'th' ('' = detect). prompt: names, terms or spelling hints.
    Results are cached by file and settings; force=True transcribes again. A long file returns status 'running'
    and a job_id; call get_transcription(job_id) until it is done. Transcripts are also saved as .md/.srt/.json."""
    if not allowed(path):
        return _refuse(path)
    if not os.path.isfile(path):
        return {"error": f"no such file: {path}"}
    key = cache_key(path, language, prompt)
    base = out_base(path, key)
    job_id = key
    cached = _f(base, ".json")
    if not force and cached.exists():
        data = json.loads(cached.read_text(encoding="utf-8"))
        job = {"job_id": job_id, "path": path, "status": "done", "cached": True, "model": data.get("model"),
               "duration_s": data.get("duration_s"), "result": data,
               "files": {"markdown": str(_f(base, ".md")), "srt": str(_f(base, ".srt")), "json": str(cached)}}
        JOBS[job_id] = job
        return reply(job)
    job = JOBS.get(job_id)
    if job is None or job["status"] in ("failed",) or (force and job["status"] == "done"):
        job = {"job_id": job_id, "path": path, "status": "queued", "started": time.strftime("%H:%M:%S")}
        JOBS[job_id] = job
        t = threading.Thread(target=_run, args=(job, path, language, prompt, base), daemon=True)
        job["thread"] = t
        t.start()
    deadline = time.time() + WAIT_MAX
    while job["status"] in ("queued", "running") and time.time() < deadline:
        time.sleep(0.25)
    return reply(job)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True))
def get_transcription(job_id: str, offset: int = 0, wait_seconds: int = 30) -> dict:
    """Status and transcript of a transcription job. Waits up to wait_seconds (max 50) while it runs.
    Long transcripts come in pages: pass the returned next_offset to read on."""
    job = JOBS.get(job_id)
    if job is None:
        return {"error": f"unknown job_id {job_id}; call transcribe_recording again (finished transcripts are cached)"}
    deadline = time.time() + max(0, min(wait_seconds, WAIT_MAX))
    while job["status"] in ("queued", "running") and time.time() < deadline:
        time.sleep(0.25)
    return reply(job, max(0, offset))


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True))
def whisper_status() -> dict:
    """Which model is loaded, where recordings are read from and transcripts written, and recent jobs."""
    return {"loaded": ENGINE.model is not None, "model": ENGINE.desc or f"{GPU_MODEL} (not loaded yet)",
            "roots": ROOTS, "recordings": RECORDINGS, "transcripts": str(TRANSCRIPTS),
            "jobs": [{k: v for k, v in j.items() if k not in ("result", "thread")} for j in list(JOBS.values())[-10:]]}


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)   # stdout carries the protocol; logs go to stderr
