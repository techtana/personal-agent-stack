"""OpenAI-compatible speech to text on voice typing's control port, for the microphone in Open WebUI's chat box.

    POST /v1/audio/transcriptions      Authorization: Bearer <LITELLM_MASTER_KEY>
                                       multipart/form-data: file (required), model, language, prompt, response_format
    -> {"text": "..."} (response_format json, the default), or the text itself (response_format text)

Open WebUI 0.12 with speech-to-text engine "openai" (request format multipart) posts its recording unchanged when
ffmpeg is not installed, as on SEKAIHOME: webm/opus from Chrome and Edge, ogg/opus from Firefox, mp4/aac from Safari,
wav; audio files dropped into a chat as mp3, m4a, flac and the like. PyAV in the voice typing environment decodes all
of them (checked with PyAV 17.0.0, 2026-11-07). aiohttp streams the file, so the body arrives with
Transfer-Encoding: chunked.

The request runs on the same Engine as voice typing: one Whisper model on the GPU, one decode at a time. The engine
records each call for the tray's Usage tab (source voice-typing), naming the caller from its User-Agent as the tray
names gateway clients (Open WebUI's aiohttp -> "Open WebUI"). The audio stays in memory; neither it nor the text is
written or logged.

The key is the gateway's LITELLM_MASTER_KEY, which Open WebUI already holds for its chat models; without one in the
app's environment or .env every request is refused. Origin and Host checks (control.check_request) come first.
Standard library only at import time: the tray imports control.py, which imports this module.
"""
from __future__ import annotations

import hmac
import io
import json
from dataclasses import dataclass
from email.message import Message
from email.utils import collapse_rfc2231_value
from typing import BinaryIO, Callable, Mapping

ROUTE = "v1/audio/transcriptions"
MAX_FILE_BYTES = 25 * 1024 * 1024           # OpenAI's limit; Open WebUI cuts longer audio into pieces under 20 MB
MAX_BODY_BYTES = MAX_FILE_BYTES + 256 * 1024  # plus the other fields and the multipart framing
MAX_PROMPT_CHARS = 4000                     # Whisper keeps only the last 223 prompt tokens anyway
RESPONSE_FORMATS = ("json", "text")
KNOWN_FIELDS = ("file", "model", "language", "prompt", "response_format", "temperature")

# transcribe(audio file bytes, language=..., prompt=..., client=...) -> text; raises ApiError for a request it refuses.
Transcriber = Callable[..., str]


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
    language: str
    prompt: str
    response_format: str


# ---------------------------------------------------------------- the key

def check_key(headers: Mapping[str, str], key: str) -> None:
    """Raise ApiError unless the request carries `Authorization: Bearer <key>` (compared in constant time)."""
    if not key:
        raise ApiError(503, "voice typing has no LITELLM_MASTER_KEY to check requests with; add it to .env and "
                            "restart voice typing", code="no_key_configured")
    lower = {k.lower(): v for k, v in headers.items()}
    scheme, _, given = (lower.get("authorization") or "").strip().partition(" ")
    if scheme.lower() != "bearer" or not given.strip():
        raise ApiError(401, "send the gateway key as Authorization: Bearer <LITELLM_MASTER_KEY>", code="missing_key")
    if not hmac.compare_digest(given.strip().encode("utf-8"), key.encode("utf-8")):
        raise ApiError(401, "the key is not this stack's LITELLM_MASTER_KEY", code="invalid_api_key")


# ---------------------------------------------------------------- the body

def iter_body(rfile: BinaryIO, headers: Mapping[str, str], limit: int = MAX_BODY_BYTES):
    """The request body in pieces, from Content-Length or Transfer-Encoding: chunked (which wins when both are sent,
    RFC 9112 6.3). Raises ApiError for a missing length, a body over `limit` or a broken chunk."""
    lower = {k.lower(): v for k, v in headers.items()}
    encoding = (lower.get("transfer-encoding") or "").strip().lower()
    if encoding:
        if encoding != "chunked":
            raise ApiError(501, f"transfer encoding {encoding!r} is not supported; send chunked or Content-Length")
        yield from _chunks(rfile, limit)
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
        yield piece


def _chunks(rfile: BinaryIO, limit: int):
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
            yield piece
        if rfile.read(2) != b"\r\n":
            raise ApiError(400, "a chunk of the chunked body does not end with CRLF")


def read_body(rfile: BinaryIO, headers: Mapping[str, str], limit: int = MAX_BODY_BYTES) -> bytes:
    return b"".join(iter_body(rfile, headers, limit))


def discard_body(rfile: BinaryIO, headers: Mapping[str, str], limit: int = MAX_BODY_BYTES) -> None:
    """Read a refused request to its end without keeping it, so the client is still sending when the answer comes:
    closing a socket with unread data resets the connection on Windows, and the client would see a reset instead of
    the reason. Gives up quietly on a body that is malformed or too large."""
    try:
        for _ in iter_body(rfile, headers, limit):
            pass
    except (ApiError, OSError):
        pass


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

def decode_audio(data: bytes):
    """Float32 mono 16 kHz samples from any container PyAV reads (in the voice typing environment only)."""
    import av
    from faster_whisper.audio import decode_audio as decode

    try:
        return decode(io.BytesIO(data), sampling_rate=16000)
    except (av.error.FFmpegError, ValueError, IndexError) as e:
        raise ApiError(400, "the file is not audio that can be read (webm, ogg, wav, mp3, m4a, mp4 and flac work): "
                            f"{type(e).__name__}", param="file", code="invalid_audio") from None


def transcribe_with(engine, data: bytes, *, language: str = "", prompt: str = "", client: str = "") -> str:
    """The Transcriber voice typing serves: decode the file, then run the shared Engine, which records the call for
    the Usage tab. A file without samples gives no text and runs no model."""
    audio = decode_audio(data)
    if not len(audio):
        return ""
    try:
        return engine.transcribe(audio, prompt=prompt, language=language, client=client)[0]
    except RuntimeError as e:
        if engine.state == "ready":
            raise
        raise ApiError(503, f"Whisper is not ready: {engine.note or e}", code="model_not_ready") from None


def client_name(user_agent: str) -> str:
    """Who asked, as the tray's Usage tab names gateway clients: Open WebUI's aiohttp -> 'Open WebUI', curl -> 'curl',
    agent-stack-<id> -> its component."""
    from .. import usage

    return usage.client_of({"user_agent": user_agent or ""})


# ---------------------------------------------------------------- one request

def respond(headers: Mapping[str, str], rfile: BinaryIO, key: str, transcribe: Transcriber | None,
            log: Callable[[str], None] = lambda m: None) -> tuple[int, str, bytes]:
    """(status, content type, body) for a POST /v1/audio/transcriptions whose Origin, Host and method were checked."""
    try:
        try:
            if transcribe is None:
                raise ApiError(503, "this copy of voice typing does not serve transcriptions")
            check_key(headers, key)
        except ApiError:
            discard_body(rfile, headers)
            raise
        lower = {k.lower(): v for k, v in headers.items()}
        req = parse_request(parse_form(read_body(rfile, headers), lower.get("content-type", "")))
        text = transcribe(req.audio, language=req.language, prompt=req.prompt,
                          client=client_name(lower.get("user-agent", "")))
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
