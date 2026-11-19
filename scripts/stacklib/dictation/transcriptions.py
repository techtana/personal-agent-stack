"""OpenAI-compatible speech to text on voice typing's control port, for the microphone in Open WebUI's chat box.

    POST /v1/audio/transcriptions      Authorization: Bearer <DICTATION_BEARER>
                                       multipart/form-data: file (required), model, language, prompt, response_format
    -> {"text": "..."} (response_format json, the default), or the text itself (response_format text)

Open WebUI 0.12 with speech-to-text engine "openai" (request format multipart) posts its recording unchanged when
ffmpeg is not installed, as on the reference machine: webm/opus from Chrome and Edge, ogg/opus from Firefox,
mp4/aac from Safari, wav; audio files dropped into a chat as mp3, m4a, flac and the like. PyAV in the voice typing
environment decodes all of them (checked with PyAV 17.0.0, 2026-11-07). aiohttp streams the file, so the body
arrives with Transfer-Encoding: chunked.

The request runs on the same Engine as voice typing: one Whisper model on the GPU, one decode at a time. The engine
records each call for the tray's Usage tab (source voice-typing), naming the caller from its User-Agent as the tray
names gateway clients (Open WebUI's aiohttp -> "Open WebUI"). The audio stays in memory; neither it nor the text is
written or logged. Without a language field the language is detected, as OpenAI's API does (voice typing's own
Language setting is for dictation); Open WebUI sends its user's Speech-to-Text Language when one is set.

Limits, because a small file can decode to hours of audio and the model is shared with dictation: 25 MB per upload,
30 minutes of audio, one request at a time (others wait up to two minutes), two minutes to send the body.

The key is DICTATION_BEARER (.env), its own key rather than the gateway's: when voice typing is off, any local
program could listen on its port and receive what Open WebUI sends. Without a key every request is refused. Origin and
Host checks (control.check_request) come first. Standard library only at import time: the tray imports control.py,
which imports this module.
"""
from __future__ import annotations

import hmac
import io
import json
import threading
import time
from dataclasses import dataclass
from email.message import Message
from email.utils import collapse_rfc2231_value
from typing import BinaryIO, Callable, Mapping

ROUTE = "v1/audio/transcriptions"
MAX_FILE_BYTES = 25 * 1024 * 1024           # OpenAI's limit; Open WebUI cuts longer audio into pieces under 20 MB
MAX_BODY_BYTES = MAX_FILE_BYTES + 256 * 1024  # plus the other fields and the multipart framing
MAX_AUDIO_S = 30 * 60                       # decoded length; longer recordings belong to the recordings server
MAX_PROMPT_CHARS = 4000                     # Whisper keeps only the last 223 prompt tokens anyway
READ_DEADLINE_S = 120.0                     # to send the whole body; a local upload of 25 MB takes well under 1 s
QUEUE_WAIT_S = 120.0                        # for the request before it, then 503
RESPONSE_FORMATS = ("json", "text")
KNOWN_FIELDS = ("file", "model", "language", "prompt", "response_format", "temperature")
RATE = 16000

# transcribe(audio file bytes, language=..., prompt=..., client=...) -> text; raises ApiError for a request it refuses.
Transcriber = Callable[..., str]

_turn = threading.BoundedSemaphore(1)  # one upload read, decoded and transcribed at a time


class ApiError(Exception):
    """A refusal with its HTTP status, answered in OpenAI's error shape so Open WebUI shows the message."""

    def __init__(self, status: int, message: str, param: str | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.status, self.message, self.param, self.code = status, message, param, code

    def body(self) -> dict:
        kind = "server_error" if self.status >= 500 else "invalid_request_error"
        return {"error": {"message": self.message, "type": kind, "param": self.param, "code": self.code}}


@dataclass(frozen=True)
class Part:
    name: str
    filename: str | None
    content_type: str
    data: bytes


@dataclass(frozen=True)
class Request:
    audio: bytes
    model: str
    language: str  # '' when none was given: detect it
    prompt: str
    response_format: str


# ---------------------------------------------------------------- the key

def check_key(headers: Mapping[str, str], key: str) -> None:
    """Raise ApiError unless the request carries `Authorization: Bearer <key>` (compared in constant time)."""
    if not key:
        raise ApiError(503, "voice typing has no DICTATION_BEARER to check requests with; run `uv run "
                            "scripts/stack.py media provision`, which adds one to .env", code="no_key_configured")
    lower = {k.lower(): v for k, v in headers.items()}
    scheme, _, given = (lower.get("authorization") or "").strip().partition(" ")
    if scheme.lower() != "bearer" or not given.strip():
        raise ApiError(401, "send voice typing's key as Authorization: Bearer <DICTATION_BEARER>", code="missing_key")
    if not hmac.compare_digest(given.strip().encode("utf-8"), key.encode("utf-8")):
        raise ApiError(401, "the key is not this stack's DICTATION_BEARER", code="invalid_api_key")


# ---------------------------------------------------------------- the body

def iter_body(rfile: BinaryIO, headers: Mapping[str, str], limit: int = MAX_BODY_BYTES,
              deadline_s: float = READ_DEADLINE_S):
    """The request body in pieces, from Content-Length or Transfer-Encoding: chunked (which wins when both are sent,
    RFC 9112 6.3). Raises ApiError for a missing length, a body over `limit`, a broken chunk, or a body that takes
    longer than `deadline_s` to arrive (each socket read has its own timeout as well)."""
    lower = {k.lower(): v for k, v in headers.items()}
    deadline = time.monotonic() + deadline_s
    encoding = (lower.get("transfer-encoding") or "").strip().lower()
    if encoding:
        if encoding != "chunked":
            raise ApiError(501, f"transfer encoding {encoding!r} is not supported; send chunked or Content-Length")
        yield from _chunks(rfile, limit, deadline)
        return
    raw = (lower.get("content-length") or "").strip()
    if not raw:
        raise ApiError(411, "send Content-Length or Transfer-Encoding: chunked")
    if not (raw.isascii() and raw.isdigit()):  # isdigit alone takes '²', which int() refuses
        raise ApiError(400, "Content-Length is not a number")
    if len(raw) > 15 or int(raw) > limit:  # int() refuses more than 4,300 digits
        raise ApiError(413, f"the request is larger than {limit // (1024 * 1024)} MB", code="too_large")
    left = int(raw)
    while left:
        piece = rfile.read(min(left, 1 << 16))
        if not piece:
            raise ApiError(400, "the request body ended early")
        left -= len(piece)
        _on_time(deadline)
        yield piece


def _on_time(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise ApiError(408, "the upload took too long", code="timeout")


def _chunks(rfile: BinaryIO, limit: int, deadline: float):
    total = 0
    while True:
        line = rfile.readline(1024)
        if not line.endswith(b"\n"):
            raise ApiError(400, "the chunked body ended early or has a malformed chunk size")
        size_text = line.split(b";", 1)[0].strip()
        if not size_text or any(c not in b"0123456789abcdefABCDEF" for c in size_text):
            raise ApiError(400, "malformed chunk size in the chunked body")
        size = int(size_text, 16)
        if size == 0:
            for _ in range(32):  # trailer fields, then the blank line that ends the body
                trailer = rfile.readline(8192)
                if trailer in (b"\r\n", b"\n", b""):
                    return
            raise ApiError(400, "too many trailer fields after the chunked body")
        total += size
        if total > limit:
            raise ApiError(413, f"the request is larger than {limit // (1024 * 1024)} MB", code="too_large")
        left = size
        while left:
            piece = rfile.read(min(left, 1 << 16))
            if not piece:
                raise ApiError(400, "the chunked body ended early")
            left -= len(piece)
            _on_time(deadline)
            yield piece
        if rfile.read(2) != b"\r\n":
            raise ApiError(400, "a chunk of the chunked body does not end with CRLF")


def read_body(rfile: BinaryIO, headers: Mapping[str, str], limit: int = MAX_BODY_BYTES,
              deadline_s: float = READ_DEADLINE_S) -> bytes:
    return b"".join(iter_body(rfile, headers, limit, deadline_s))


# ---------------------------------------------------------------- multipart/form-data

def header_params(value: str) -> tuple[str, dict[str, str]]:
    """('multipart/form-data', {'boundary': ...}) from a header value; quoted and RFC 2231 values unfolded."""
    msg = Message()
    msg["x"] = value or ""
    params = msg.get_params(header="x") or [("", "")]
    main = params[0][0].strip().lower()
    out: dict[str, str] = {}
    for k, v in params[1:]:
        out[k.strip().lower()] = collapse_rfc2231_value(v)
    return main, out


def parse_form(body: bytes, content_type: str, max_parts: int = 32) -> dict[str, Part]:
    """Fields of a multipart/form-data body (RFC 7578) by name. Raises ApiError for anything malformed."""
    kind, params = header_params(content_type)
    if kind != "multipart/form-data":
        raise ApiError(415, "send the audio as multipart/form-data with a file field", code="unsupported_media_type")
    boundary = params.get("boundary", "")
    if not boundary or len(boundary) > 200:
        raise ApiError(400, "the multipart body has no boundary")
    delimiter = b"--" + boundary.encode("latin-1", "replace")
    if body.startswith(delimiter):
        start = len(delimiter)
    else:  # a preamble before the first delimiter
        at = body.find(b"\r\n" + delimiter)
        if at < 0:
            raise ApiError(400, "the multipart body does not contain its boundary")
        start = at + 2 + len(delimiter)
    parts: dict[str, Part] = {}
    for index, piece in enumerate(body[start:].split(b"\r\n" + delimiter)):
        if piece.startswith(b"--"):  # the closing delimiter; anything after it is an epilogue
            return parts
        if index >= max_parts:
            raise ApiError(400, "too many form fields")
        eol = piece.find(b"\r\n")
        if eol < 0 or piece[:eol].strip(b" \t"):
            raise ApiError(400, "malformed multipart body")
        rest = piece[eol + 2:]
        if rest.startswith(b"\r\n"):
            head, content = b"", rest[2:]
        else:
            head, sep, content = rest.partition(b"\r\n\r\n")
            if not sep:
                raise ApiError(400, "a multipart part has no blank line after its headers")
        fields: dict[str, str] = {}
        for line in head.split(b"\r\n") if head else ():
            name, colon, value = line.partition(b":")
            if not colon:
                raise ApiError(400, "malformed header in a multipart part")
            fields[name.strip().lower().decode("latin-1")] = value.strip().decode("utf-8", "replace")
        disposition, dparams = header_params(fields.get("content-disposition", ""))
        name = dparams.get("name", "")
        if disposition != "form-data" or not name:
            raise ApiError(400, "a multipart part has no Content-Disposition: form-data name")
        if name in parts:
            if name in KNOWN_FIELDS:
                raise ApiError(400, f"the field {name!r} appears more than once", param=name)
            continue  # repeated unknown fields (timestamp_granularities[]) are ignored like the field itself
        parts[name] = Part(name, dparams.get("filename"), fields.get("content-type", ""), content)
    raise ApiError(400, "the multipart body has no closing boundary")


def _text(form: dict[str, Part], name: str, limit: int = 200) -> str:
    part = form.get(name)
    if part is None:
        return ""
    try:
        value = part.data.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise ApiError(400, f"the field {name!r} is not UTF-8 text", param=name) from None
    if len(value) > limit:
        raise ApiError(400, f"the field {name!r} is longer than {limit} characters", param=name)
    return value


def normalize_language(value: str) -> str:
    """'' for automatic detection; a Whisper code from 'en', 'EN', 'en-US' or 'pt_BR'. Raises ApiError otherwise."""
    from .models import WHISPER_LANGUAGES

    code = value.strip().lower().replace("_", "-").split("-", 1)[0]
    if code in ("", "auto"):
        return ""
    if code not in WHISPER_LANGUAGES:
        raise ApiError(400, f"language {value!r} is not a Whisper language code (ISO 639-1, such as en or th)",
                       param="language", code="invalid_language")
    return code


def parse_request(form: dict[str, Part]) -> Request:
    """The fields this endpoint uses, checked. `model` is accepted and ignored: voice typing has one Whisper model
    (dictation.model), and Open WebUI sends whatever its admin page holds. `temperature` is ignored as well."""
    part = form.get("file")
    if part is None:
        raise ApiError(400, "the request has no file field with the audio", param="file")
    if not part.data:
        raise ApiError(400, "the audio file is empty", param="file")
    if len(part.data) > MAX_FILE_BYTES:
        raise ApiError(413, f"the audio file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB", param="file",
                       code="too_large")
    fmt = _text(form, "response_format").lower() or "json"
    if fmt not in RESPONSE_FORMATS:
        raise ApiError(400, f"response_format {fmt!r} is not supported here; use json or text", param="response_format")
    return Request(audio=part.data, model=_text(form, "model"), language=normalize_language(_text(form, "language")),
                   prompt=_text(form, "prompt", limit=MAX_PROMPT_CHARS), response_format=fmt)


# ---------------------------------------------------------------- audio

def decode_audio(data: bytes, max_seconds: float | None = None):
    """Float32 mono 16 kHz samples from any container PyAV reads (in the voice typing environment only).

    Decodes frame by frame and stops with 413 as soon as the audio passes `max_seconds` (or at once when the container
    says it is longer): 25 MB of FLAC silence or of very low-bitrate Opus expands to hours, gigabytes of samples. A
    damaged or cut-off file gives what decoded before the damage, as faster-whisper's own decoder does."""
    import av
    import numpy as np

    max_seconds = MAX_AUDIO_S if max_seconds is None else max_seconds
    limit = int(max_seconds * RATE)
    too_long = ApiError(413, f"the audio is longer than {max_seconds / 60:g} minutes; for long recordings use the "
                             "recordings server", param="file", code="audio_too_long")
    unreadable = "the file is not audio that can be read (webm, ogg, wav, mp3, m4a, mp4 and flac work)"
    pieces: list = []
    total = 0

    def keep(frames) -> None:
        nonlocal total
        for out in frames:
            samples = out.to_ndarray().reshape(-1)
            total += samples.size
            if total > limit:
                raise too_long
            pieces.append(samples)

    try:
        container = av.open(io.BytesIO(data), mode="r", metadata_errors="ignore")
    except (av.error.FFmpegError, ValueError, OSError) as e:
        raise ApiError(400, f"{unreadable}: {type(e).__name__}", param="file", code="invalid_audio") from None
    with container:
        if not container.streams.audio:
            raise ApiError(400, "the file has no audio track", param="file", code="invalid_audio")
        if container.duration and container.duration / av.time_base > max_seconds + 1:
            raise too_long
        resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)
        try:
            for packet in container.demux(container.streams.audio[0]):
                for frame in packet.decode():
                    keep(resampler.resample(frame))
        except (av.error.FFmpegError, ValueError) as e:
            if not pieces:
                raise ApiError(400, f"{unreadable}: {type(e).__name__}", param="file", code="invalid_audio") from None
        try:
            keep(resampler.resample(None))  # what the resampler still holds
        except (av.error.FFmpegError, ValueError):
            pass
    if not pieces:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(pieces).astype(np.float32) / 32768.0


def transcribe_with(engine, data: bytes, *, language: str = "", prompt: str = "", client: str = "") -> str:
    """The Transcriber voice typing serves: decode the file, then run the shared Engine, which records the call for
    the Usage tab. No language means detect it ("auto"), not voice typing's own setting. A file without samples
    gives no text and runs no model."""
    from .. import usage_log

    audio = decode_audio(data)
    if not len(audio):
        return ""
    try:
        return engine.transcribe(audio, prompt=prompt, language=language or "auto", client=client)[0]
    except RuntimeError as e:
        if engine.state == "ready":
            raise
        # The load error can name folders; the reply only needs what went wrong.
        raise ApiError(503, f"The speech model is not ready: {usage_log.scrub(engine.note or str(e))}",
                       code="model_not_ready") from None


def client_name(user_agent: str) -> str:
    """Who asked, as the tray's Usage tab names gateway clients: Open WebUI's aiohttp -> 'Open WebUI', curl -> 'curl',
    agent-stack-<id> -> its component."""
    from .. import usage

    return usage.client_of({"user_agent": user_agent or ""})


# ---------------------------------------------------------------- one request

def respond(headers: Mapping[str, str], rfile: BinaryIO, key: str | Callable[[], str], transcribe: Transcriber | None,
            log: Callable[[str], None] = lambda m: None) -> tuple[int, str, bytes]:
    """(status, content type, body) for a POST /v1/audio/transcriptions whose Origin, Host and method were checked.
    `key` may be a function, so a key added to .env after voice typing started is used without a restart. A refusal
    can leave the body unread; the server reads it after answering (control.py), so the caller sees the reason."""
    try:
        if transcribe is None:
            raise ApiError(503, "this copy of voice typing does not serve transcriptions")
        check_key(headers, key() if callable(key) else key)
        if not _turn.acquire(timeout=QUEUE_WAIT_S):
            raise ApiError(503, "voice typing is still busy with an earlier transcription; try again", code="busy")
        try:
            lower = {k.lower(): v for k, v in headers.items()}
            req = parse_request(parse_form(read_body(rfile, headers), lower.get("content-type", "")))
            text = transcribe(req.audio, language=req.language, prompt=req.prompt,
                              client=client_name(lower.get("user-agent", "")))
        finally:
            _turn.release()
    except ApiError as e:
        if e.status >= 500:
            log(f"[dictation] transcription request refused: {e.message}")
        return e.status, "application/json", json.dumps(e.body()).encode("utf-8")
    except Exception as e:  # noqa: BLE001 - answer, never kill the server thread
        from .. import usage_log

        # The reply names only the error's type; the log adds its message without file paths.
        log(f"[dictation] transcription request failed: {type(e).__name__}: {usage_log.scrub(str(e))[:200]}")
        err = ApiError(500, f"transcription failed ({type(e).__name__}); see .run/logs/dictation.log")
        return 500, "application/json", json.dumps(err.body()).encode("utf-8")
    if req.response_format == "text":
        return 200, "text/plain; charset=utf-8", text.encode("utf-8")
    return 200, "application/json", json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
