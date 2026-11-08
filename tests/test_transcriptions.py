r"""Open WebUI's microphone on voice typing's Whisper: the OpenAI-compatible transcription endpoint on the dictation
port (scripts/stacklib/dictation/transcriptions.py, control.py), the Open WebUI settings that point at it
(services.openwebui_stt_settings / _env, `stack.py media provision`), and the Usage tab's note while Open WebUI still
runs its own Whisper. Nothing here needs a model or a microphone: the transcriber is a stand-in. The decoder tests
need PyAV and numpy and run in the voice typing environment:
    D:\media\dictation\.venv\Scripts\python.exe -m unittest discover -s tests -p test_transcriptions.py
"""
from __future__ import annotations

import http.client
import importlib.util
import io
import json
import os
import socket
import sqlite3
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import dictation, media, services, usage  # noqa: E402
from stacklib import profile as prof  # noqa: E402
from stacklib.dictation import control, transcriptions as t  # noqa: E402

KEY = "sk-test-0123456789"
BOUNDARY = "6f9b1c0e8a2d4e5fa1b2c3d4e5f60718"  # aiohttp's boundaries are uuid4 hex
# A recording's first bytes (EBML, as in a browser's webm), then bytes that look like multipart framing but are not
# this body's boundary, then a trailing CRLF that belongs to the file.
AUDIO = b"\x1aE\xdf\xa3\x9fB\x86\x81\x01" + b"\r\n--not-the-boundary\r\n" + bytes(range(256)) * 40 + b"\r\n"
AIOHTTP_UA = "Python/3.11 aiohttp/3.13.2"


def form(fields: dict[str, str] | None = None, audio: bytes | None = AUDIO, filename: str = "0b6e.webm",
         boundary: str = BOUNDARY, preamble: bytes = b"", epilogue: bytes = b"") -> bytes:
    """A multipart body laid out the way aiohttp's FormData writes it (Content-Type before Content-Disposition)."""
    out = [preamble]
    for name, value in (fields if fields is not None else {"model": "large-v3-turbo"}).items():
        out.append(f'--{boundary}\r\nContent-Type: text/plain; charset=utf-8\r\n'
                   f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode() + value.encode("utf-8") + b"\r\n")
    if audio is not None:
        out.append(f'--{boundary}\r\nContent-Type: application/octet-stream\r\n'
                   f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n\r\n'.encode()
                   + audio + b"\r\n")
    out.append(f"--{boundary}--\r\n".encode() + epilogue)
    return b"".join(out)


def ctype(boundary: str = BOUNDARY) -> str:
    return f"multipart/form-data; boundary={boundary}"


def chunked(body: bytes, size: int = 1000, ext: bytes = b"") -> bytes:
    pieces = [body[i:i + size] for i in range(0, len(body), size)]
    return b"".join(b"%x%s\r\n%s\r\n" % (len(p), ext, p) for p in pieces) + b"0\r\n\r\n"


def headers(body: bytes, **extra) -> dict[str, str]:
    return {"Host": "127.0.0.1:8790", "Authorization": f"Bearer {KEY}", "Content-Type": ctype(),
            "Content-Length": str(len(body)), "User-Agent": AIOHTTP_UA, **extra}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class MultipartBodies(unittest.TestCase):
    def test_fields_and_binary_audio_survive_exactly(self):
        parts = t.parse_form(form({"model": "large-v3-turbo", "language": "en"}), ctype())
        self.assertEqual(parts["file"].data, AUDIO)
        self.assertEqual(parts["file"].filename, "0b6e.webm")
        self.assertEqual(parts["model"].data, b"large-v3-turbo")
        self.assertEqual(parts["language"].data, b"en")

    def test_preamble_epilogue_quoted_boundary_and_encoded_filename(self):
        body = form(preamble=b"ignored preamble\r\n", epilogue=b"ignored epilogue")
        self.assertEqual(t.parse_form(body, f'multipart/form-data; boundary="{BOUNDARY}"')["file"].data, AUDIO)
        encoded = body.replace(b'filename="0b6e.webm"', b"filename*=utf-8''%E2%82%AC.webm")
        self.assertEqual(t.parse_form(encoded, ctype())["file"].filename, "\u20ac.webm")

    def test_refusals(self):
        cases = {
            "not multipart": (form(), "application/json", 415),
            "no boundary parameter": (form(), "multipart/form-data", 400),
            "boundary not in the body": (form(boundary="other"), ctype(), 400),
            "cut off before the closing boundary": (form()[:-40], ctype(), 400),
            "part without a name": (form().replace(b'; name="model"', b""), ctype(), 400),
            "part without headers": (form().replace(b'Content-Type: text/plain; charset=utf-8\r\n'
                                                    b'Content-Disposition: form-data; name="model"\r\n', b""),
                                     ctype(), 400),
        }
        for label, (body, content_type, status) in cases.items():
            with self.subTest(label), self.assertRaises(t.ApiError) as cm:
                t.parse_form(body, content_type)
            self.assertEqual(cm.exception.status, status, label)

    def test_a_second_file_is_refused_and_unknown_repeats_are_ignored(self):
        two_files = form().replace(f"--{BOUNDARY}--".encode(), (
            f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="file"; filename="b.wav"\r\n\r\nxx\r\n'
            f"--{BOUNDARY}--").encode())
        with self.assertRaises(t.ApiError) as cm:
            t.parse_form(two_files, ctype())
        self.assertEqual(cm.exception.param, "file")
        repeats = form({"timestamp_granularities[]": "word"}).replace(f"--{BOUNDARY}--".encode(), (
            f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="timestamp_granularities[]"\r\n\r\nsegment\r\n'
            f"--{BOUNDARY}--").encode())
        self.assertEqual(t.parse_form(repeats, ctype())["timestamp_granularities[]"].data, b"word")

    def test_too_many_parts(self):
        with self.assertRaises(t.ApiError):
            t.parse_form(form({f"f{i}": "x" for i in range(40)}), ctype())


class RequestFields(unittest.TestCase):
    def parse(self, **fields) -> t.Request:
        return t.parse_request(t.parse_form(form(fields), ctype()))

    def refused(self, body: bytes) -> t.ApiError:
        with self.assertRaises(t.ApiError) as cm:
            t.parse_request(t.parse_form(body, ctype()))
        return cm.exception

    def test_defaults(self):
        req = self.parse(model="whisper-1")  # Open WebUI sends whatever model its admin page holds; it is ignored
        self.assertEqual((req.audio, req.language, req.prompt, req.response_format), (AUDIO, "", "", "json"))

    def test_languages_are_whisper_codes(self):
        for given, want in (("en", "en"), ("EN", "en"), ("en-US", "en"), ("pt_BR", "pt"), ("auto", ""), ("", ""),
                            ("yue", "yue"), ("th", "th")):
            with self.subTest(given):
                self.assertEqual(self.parse(language=given).language, want)
        err = self.refused(form({"language": "English"}))
        self.assertEqual((err.status, err.param), (400, "language"))

    def test_response_formats(self):
        self.assertEqual(self.parse(response_format="TEXT").response_format, "text")
        for fmt in ("verbose_json", "srt", "vtt"):
            with self.subTest(fmt):
                self.assertEqual(self.refused(form({"response_format": fmt})).param, "response_format")

    def test_audio_must_be_there_and_not_too_big(self):
        self.assertEqual(self.refused(form(audio=None)).param, "file")
        self.assertEqual(self.refused(form(audio=b"")).param, "file")
        with mock.patch.object(t, "MAX_FILE_BYTES", 100):
            self.assertEqual(self.refused(form()).status, 413)

    def test_text_fields_are_utf8_and_bounded(self):
        self.assertEqual(self.parse(prompt="Grüße, ThinkPad").prompt, "Grüße, ThinkPad")
        bad = form({"prompt": "x"}).replace(b"\r\n\r\nx\r\n", b"\r\n\r\n\xff\xfe\r\n")
        self.assertEqual(self.refused(bad).param, "prompt")
        self.assertEqual(self.refused(form({"prompt": "x" * (t.MAX_PROMPT_CHARS + 1)})).param, "prompt")


class RequestBodies(unittest.TestCase):
    def test_content_length(self):
        body = form()
        self.assertEqual(t.read_body(io.BytesIO(body + b"next request"), {"Content-Length": str(len(body))}), body)

    def test_chunked_with_extensions_and_trailers(self):
        body = form()
        wire = chunked(body, 777, ext=b";name=value").replace(b"0\r\n\r\n", b"0\r\nX-Trailer: 1\r\n\r\n")
        h = {"Transfer-Encoding": "chunked", "Content-Length": "5"}  # chunked wins over a stray length
        self.assertEqual(t.read_body(io.BytesIO(wire), h), body)

    def test_refused_bodies(self):
        good = chunked(b"x" * 3000)
        cases = {
            "no length at all": (b"abc", {}, 411),
            "length is not a number": (b"abc", {"Content-Length": "3x"}, 400),
            "a digit int() refuses": (b"abc", {"Content-Length": "²"}, 400),
            "thousands of digits": (b"", {"Content-Length": "9" * 5000}, 413),
            "shorter than its length": (b"abc", {"Content-Length": "10"}, 400),
            "over the limit": (b"", {"Content-Length": str(t.MAX_BODY_BYTES + 1)}, 413),
            "unknown transfer encoding": (b"", {"Transfer-Encoding": "gzip, chunked"}, 501),
            "bad chunk size": (b"zz\r\nabc\r\n0\r\n\r\n", {"Transfer-Encoding": "chunked"}, 400),
            "negative chunk size": (b"-3\r\nabc\r\n0\r\n\r\n", {"Transfer-Encoding": "chunked"}, 400),
            "chunk without its CRLF": (b"3\r\nabcX\r\n0\r\n\r\n", {"Transfer-Encoding": "chunked"}, 400),
            "chunked body cut off": (good[:1500], {"Transfer-Encoding": "chunked"}, 400),
        }
        for label, (wire, h, status) in cases.items():
            with self.subTest(label), self.assertRaises(t.ApiError) as cm:
                t.read_body(io.BytesIO(wire), h)
            self.assertEqual(cm.exception.status, status, label)
        with self.assertRaises(t.ApiError) as cm:
            t.read_body(io.BytesIO(good), {"Transfer-Encoding": "chunked"}, limit=2000)
        self.assertEqual(cm.exception.status, 413)

    def test_a_body_that_takes_too_long_is_refused(self):
        body = form()
        for h, wire in (({"Content-Length": str(len(body))}, body), ({"Transfer-Encoding": "chunked"}, chunked(body))):
            with self.subTest(h), self.assertRaises(t.ApiError) as cm:
                t.read_body(io.BytesIO(wire), h, deadline_s=-1)
            self.assertEqual(cm.exception.status, 408)


class Keys(unittest.TestCase):
    def test_bearer_key(self):
        t.check_key({"Authorization": f"Bearer {KEY}"}, KEY)
        t.check_key({"authorization": f"bearer  {KEY} "}, KEY)
        for label, h in (("none", {}), ("basic", {"Authorization": f"Basic {KEY}"}), ("empty", {"Authorization": "Bearer "}),
                         ("wrong", {"Authorization": "Bearer sk-other"}), ("prefix", {"Authorization": f"Bearer {KEY[:-1]}"})):
            with self.subTest(label), self.assertRaises(t.ApiError) as cm:
                t.check_key(h, KEY)
            self.assertEqual(cm.exception.status, 401)
            self.assertNotIn(KEY[:8], cm.exception.message)

    def test_no_key_configured_refuses_everyone(self):
        with self.assertRaises(t.ApiError) as cm:
            t.check_key({"Authorization": "Bearer "}, "")
        self.assertEqual(cm.exception.status, 503)
        self.assertIn("DICTATION_BEARER", cm.exception.message)


class Respond(unittest.TestCase):
    def setUp(self):
        self.calls: list[tuple[bytes, dict]] = []

    def fake(self, data: bytes, **kw) -> str:
        self.calls.append((data, kw))
        return "Hello from Whisper."

    def test_json_reply_and_what_the_transcriber_gets(self):
        body = form({"model": "large-v3-turbo", "language": "en-GB", "prompt": "Logseq"})
        status, content_type, out = t.respond(headers(body), io.BytesIO(body), KEY, self.fake)
        self.assertEqual((status, content_type, json.loads(out)), (200, "application/json", {"text": "Hello from Whisper."}))
        self.assertEqual(self.calls, [(AUDIO, {"language": "en", "prompt": "Logseq", "client": "Open WebUI"})])

    def test_text_reply_and_other_clients(self):
        body = form({"response_format": "text"})
        status, content_type, out = t.respond(headers(body, **{"User-Agent": "curl/8.9.1"}), io.BytesIO(body), KEY,
                                              self.fake)
        self.assertEqual((status, content_type, out), (200, "text/plain; charset=utf-8", b"Hello from Whisper."))
        self.assertEqual(self.calls[0][1]["client"], "curl")

    def test_wrong_key_runs_nothing(self):
        body = form()
        status, _, out = t.respond(headers(body, Authorization="Bearer nope"), io.BytesIO(body), KEY, self.fake)
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(out)["error"]["type"], "invalid_request_error")
        self.assertEqual(self.calls, [])

    def test_the_key_can_be_looked_up_per_request(self):
        keys = iter(["", KEY])  # added to .env after voice typing started
        body = form()
        self.assertEqual(t.respond(headers(body), io.BytesIO(body), lambda: next(keys), self.fake)[0], 503)
        self.assertEqual(t.respond(headers(body), io.BytesIO(body), lambda: next(keys), self.fake)[0], 200)

    def test_one_request_at_a_time(self):
        body = form()
        self.assertTrue(t._turn.acquire(timeout=1))  # another request is being transcribed
        try:
            with mock.patch.object(t, "QUEUE_WAIT_S", 0.05):
                status, _, out = t.respond(headers(body), io.BytesIO(body), KEY, self.fake)
        finally:
            t._turn.release()
        self.assertEqual((status, json.loads(out)["error"]["code"]), (503, "busy"))
        self.assertEqual(self.calls, [])
        self.assertEqual(t.respond(headers(body), io.BytesIO(body), KEY, self.fake)[0], 200)  # the turn was released

    def test_refusals_from_the_transcriber_keep_their_status(self):
        def refuse(data, **kw):
            raise t.ApiError(400, "the file is not audio that can be read", param="file", code="invalid_audio")

        body = form()
        status, _, out = t.respond(headers(body), io.BytesIO(body), KEY, refuse)
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(out), {"error": {"message": "the file is not audio that can be read",
                                                     "type": "invalid_request_error", "param": "file",
                                                     "code": "invalid_audio"}})

    def test_unexpected_errors_do_not_leak_their_message(self):
        def crash(data, **kw):
            raise RuntimeError(r"CUDA failed reading C:\Users\someone\secret.webm")

        body = form()
        logged: list[str] = []
        status, _, out = t.respond(headers(body), io.BytesIO(body), KEY, crash, log=logged.append)
        self.assertEqual(status, 500)
        self.assertNotIn("secret", out.decode())
        self.assertNotIn("secret", " ".join(logged))
        self.assertEqual(json.loads(out)["error"]["type"], "server_error")

    def test_without_a_transcriber(self):
        body = form()
        self.assertEqual(t.respond(headers(body), io.BytesIO(body), KEY, None)[0], 503)


class SharedEngine(unittest.TestCase):
    class Engine:
        def __init__(self, state="ready", fail: Exception | None = None):
            self.state, self.note, self.fail, self.calls = state, "Whisper could not load: no CUDA device", fail, []

        def transcribe(self, audio, **kw):
            self.calls.append((audio, kw))
            if self.fail:
                raise self.fail
            return "Hi.", "en"

    def test_decoded_audio_goes_to_the_engine_with_its_client(self):
        e = self.Engine()
        with mock.patch.object(t, "decode_audio", return_value=[0.0] * 16000):
            self.assertEqual(t.transcribe_with(e, b"webm", language="th", prompt="", client="Open WebUI"), "Hi.")
            t.transcribe_with(e, b"webm", client="Open WebUI")
        self.assertEqual(e.calls[0][1], {"prompt": "", "language": "th", "client": "Open WebUI"})
        # No language from Open WebUI: detect it, rather than voice typing's own dictation.language.
        self.assertEqual(e.calls[1][1]["language"], "auto")

    def test_a_file_without_samples_runs_no_model(self):
        e = self.Engine()
        with mock.patch.object(t, "decode_audio", return_value=[]):
            self.assertEqual(t.transcribe_with(e, b"webm"), "")
        self.assertEqual(e.calls, [])

    def test_whisper_not_loaded_is_503_with_the_reason(self):
        e = self.Engine(state="failed", fail=RuntimeError("Whisper could not load: no CUDA device"))
        with mock.patch.object(t, "decode_audio", return_value=[0.0]), self.assertRaises(t.ApiError) as cm:
            t.transcribe_with(e, b"webm")
        self.assertEqual(cm.exception.status, 503)
        self.assertIn("no CUDA device", cm.exception.message)
        e.note = r"Whisper could not load: Unable to open file 'D:\huggingface\hub\models--x\model.bin'"
        with mock.patch.object(t, "decode_audio", return_value=[0.0]), self.assertRaises(t.ApiError) as cm:
            t.transcribe_with(e, b"webm")
        self.assertNotIn("huggingface", cm.exception.message)
        ready = self.Engine(fail=RuntimeError("cuBLAS failed"))
        with mock.patch.object(t, "decode_audio", return_value=[0.0]), self.assertRaises(RuntimeError):
            t.transcribe_with(ready, b"webm")


class Server(unittest.TestCase):
    """The real control server on a free port, with a stand-in transcriber."""

    def setUp(self):
        self.port = free_port()
        self.calls: list[tuple[bytes, dict]] = []
        self.server = control.ControlServer(self.port, lambda: {"ok": True, "state": "idle"}, lambda name: {"ok": True},
                                            transcribe=lambda data, **kw: (self.calls.append((data, kw)), "Hi.")[1],
                                            api_key=KEY)
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def post(self, body, extra: dict | None = None, chunk: bool = False, path: str = "/v1/audio/transcriptions"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        h = {"Authorization": f"Bearer {KEY}", "Content-Type": ctype(), "User-Agent": AIOHTTP_UA, **(extra or {})}
        try:
            if chunk:  # as aiohttp streams Open WebUI's file: no length, Transfer-Encoding: chunked
                pieces = [body[i:i + 4096] for i in range(0, len(body), 4096)]
                conn.request("POST", path, body=iter(pieces), headers=h, encode_chunked=True)
            else:
                conn.request("POST", path, body=body, headers=h)
            r = conn.getresponse()
            return r.status, r.getheader("Content-Type"), r.read()
        finally:
            conn.close()

    def test_chunked_upload_like_open_webui(self):
        status, content_type, out = self.post(form({"model": "large-v3-turbo"}), chunk=True)
        self.assertEqual((status, content_type, json.loads(out)), (200, "application/json", {"text": "Hi."}))
        self.assertEqual(self.calls, [(AUDIO, {"language": "", "prompt": "", "client": "Open WebUI"})])

    def test_content_length_upload_and_text_format(self):
        status, content_type, out = self.post(form({"response_format": "text", "language": "de"}))
        self.assertEqual((status, out), (200, b"Hi."))
        self.assertEqual(self.calls[0][1]["language"], "de")

    def test_wrong_key_with_a_large_body_still_gets_its_answer(self):
        for _ in range(3):  # a reset shows up in some tries only
            status, _, out = self.post(form(audio=os.urandom(3 * 1024 * 1024)), {"Authorization": "Bearer wrong"})
            self.assertEqual(status, 401)
            self.assertEqual(json.loads(out)["error"]["code"], "invalid_api_key")
        self.assertEqual(self.calls, [])

    def test_an_oversized_upload_gets_its_413_although_it_was_never_read(self):
        big = form(audio=os.urandom(t.MAX_BODY_BYTES + 1024 * 1024))
        status, _, out = self.post(big)
        self.assertEqual((status, json.loads(out)["error"]["code"]), (413, "too_large"))
        status, _, out = self.post(big, chunk=True)
        self.assertEqual((status, json.loads(out)["error"]["code"]), (413, "too_large"))
        self.assertEqual(self.calls, [])

    def test_without_a_key_nobody_gets_in(self):
        self.server.stop()
        self.server = control.ControlServer(self.port, dict, lambda name: {}, transcribe=lambda data, **kw: "x",
                                            api_key=lambda: "")
        self.server.start()
        status, _, out = self.post(form())
        self.assertEqual((status, json.loads(out)["error"]["code"]), (503, "no_key_configured"))

    def test_web_pages_wrong_hosts_and_methods_are_refused(self):
        status, _, out = self.post(form(), {"Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        self.assertIn("web pages", json.loads(out)["error"]["message"])
        self.assertEqual(self.post(form(), {"Host": f"evil.example:{self.port}"})[0], 403)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", "/v1/audio/transcriptions")
            self.assertEqual(conn.getresponse().status, 405)
        finally:
            conn.close()
        self.assertEqual(self.calls, [])

    def test_health_and_actions_are_unchanged(self):
        self.assertEqual(control.call(self.port, "health")["state"], "idle")
        self.assertTrue(control.call(self.port, "toggle")["ok"])

    def test_request_rules_know_the_route(self):
        ok = {"Host": "127.0.0.1:8790"}
        self.assertIsNone(control.check_request("POST", "/v1/audio/transcriptions", ok, 8790))
        self.assertEqual(control.check_request("GET", "/v1/audio/transcriptions", ok, 8790)[0], 405)
        self.assertEqual(control.check_request("POST", "/v1/audio/translations", ok, 8790)[0], 404)


def stt_profile(tmp: str, dictation_on: bool = True, open_webui_on: bool = True, port=8790) -> dict:
    return {"name": "TEST", "data_dir": tmp, "ports": {"dictation": port, "litellm": 4000},
            "services": {"dictation": "native" if dictation_on else "off",
                         "open_webui": "native" if open_webui_on else "off"},
            "models": {}, "dictation": {"model": "large-v3-turbo"}}


class OpenWebUISettings(unittest.TestCase):
    def test_rows_point_at_voice_typing_on_this_machine(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = services.openwebui_stt_settings(stt_profile(tmp), KEY)
        self.assertEqual(rows, {"audio.stt.engine": "openai", "audio.stt.openai.api_base_url": "http://127.0.0.1:8790/v1",
                                "audio.stt.openai.api_key": KEY, "audio.stt.openai.api_request_format": "multipart",
                                "audio.stt.model": "large-v3-turbo"})

    def test_nothing_without_voice_typing_or_a_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(services.openwebui_stt_settings(stt_profile(tmp, dictation_on=False), KEY), {})
            self.assertEqual(services.openwebui_stt_env(stt_profile(tmp, dictation_on=False), KEY), {})
            self.assertEqual(services.openwebui_stt_settings(stt_profile(tmp), ""), {})

    def test_the_base_url_can_only_be_this_machine(self):
        with tempfile.TemporaryDirectory() as tmp:
            for port in (1, 8790, "8790", 65535):
                url = services.openwebui_stt_settings(stt_profile(tmp, port=port), KEY)["audio.stt.openai.api_base_url"]
                self.assertEqual(urllib.parse.urlsplit(url).hostname, "127.0.0.1", url)
            for port in ("8790@evil.example", "evil.example:80", "", 0, -1, 70000):
                with self.subTest(port=port), self.assertRaises(ValueError):
                    services.openwebui_stt_settings(stt_profile(tmp, port=port), KEY)

    def test_environment_for_a_fresh_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = services.openwebui_stt_env(stt_profile(tmp), KEY)
        self.assertEqual(env, {"AUDIO_STT_ENGINE": "openai", "AUDIO_STT_OPENAI_API_BASE_URL": "http://127.0.0.1:8790/v1",
                               "AUDIO_STT_OPENAI_API_KEY": KEY, "AUDIO_STT_OPENAI_API_REQUEST_FORMAT": "multipart",
                               "AUDIO_STT_MODEL": "large-v3-turbo"})

    def test_open_webui_starts_with_it_only_while_voice_typing_is_on(self):
        for on in (True, False):
            machine = {"name": "TESTBOX", "services": {"open_webui": "native", "dictation": "native" if on else "off",
                                                       "comfyui": "off", "kokoro": "off"}}
            with self.subTest(dictation=on), mock.patch.object(prof, "load_machine", return_value=machine), \
                    mock.patch.dict(os.environ, {"LITELLM_MASTER_KEY": "sk-gateway", "DICTATION_BEARER": KEY}), \
                    mock.patch.object(services, "load_dotenv", return_value={}), \
                    mock.patch.object(services, "tool_command", side_effect=lambda svc: [f"{svc}.exe"]):
                env = services.commands(prof.resolve_profile("TESTBOX"))["open_webui"]["env"]
                if on:
                    self.assertEqual(env["AUDIO_STT_ENGINE"], "openai")
                    self.assertTrue(env["AUDIO_STT_OPENAI_API_BASE_URL"].startswith("http://127.0.0.1:"))
                    self.assertEqual(env["AUDIO_STT_OPENAI_API_KEY"], KEY)
                    self.assertNotIn("sk-gateway", [v for k, v in env.items() if k.startswith("AUDIO_STT_")])
                else:
                    self.assertFalse([k for k in env if k.startswith("AUDIO_STT_")])


class VoiceTypingKey(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = Path(self.tmp.name) / ".env"
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(dictation.KEY_NAME, None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_added_once_and_the_rest_of_env_is_left_alone(self):
        original = "# my notes\nLITELLM_MASTER_KEY=sk-gateway\nANTHROPIC_API_KEY="  # no newline at the end
        self.env.write_text(original, encoding="utf-8", newline="\n")
        key = dictation.ensure_api_key(self.env)
        text = self.env.read_text(encoding="utf-8")
        self.assertEqual(text, original + f"\nDICTATION_BEARER={key}\n")
        self.assertGreaterEqual(len(key), 40)
        self.assertNotEqual(key, "sk-gateway")
        self.assertEqual(dictation.ensure_api_key(self.env), key)  # the second call finds it
        self.assertEqual(self.env.read_text(encoding="utf-8"), text)

    def test_a_missing_env_file_is_created(self):
        key = dictation.ensure_api_key(self.env)
        self.assertEqual(self.env.read_text(encoding="utf-8"), f"DICTATION_BEARER={key}\n")

    def test_the_installer_generates_one(self):
        from stacklib import install

        with mock.patch.object(install, "ENV_FILE", self.env), \
                mock.patch.object(install, "load_dotenv", return_value={}):
            env = install.ensure_env_file()
        self.assertTrue(env["DICTATION_BEARER"])
        self.assertNotEqual(env["DICTATION_BEARER"], env["LITELLM_MASTER_KEY"])


def openwebui_db(tmp: str, engine: str = "", base_url: str = "https://api.openai.com/v1") -> Path:
    """An Open WebUI 0.12 config table seeded the way the owner's install is (engine "", OpenAI's default URL)."""
    db = Path(tmp) / "open-webui" / "webui.db"
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.execute('CREATE TABLE config ("key" TEXT NOT NULL, value JSON NOT NULL, updated_at BIGINT, PRIMARY KEY ("key"))')
    con.executemany("insert into config values (?, ?, 0)", [
        ("audio.stt.engine", json.dumps(engine)), ("audio.stt.openai.api_base_url", json.dumps(base_url)),
        ("audio.stt.openai.api_key", '""'), ("audio.stt.openai.api_request_format", '"multipart"'),
        ("audio.stt.model", '""'), ("audio.stt.whisper_model", '"base"'), ("ui.other", '"kept"')])
    con.commit()
    con.close()
    return db


def config_rows(db: Path) -> dict:
    con = sqlite3.connect(db)
    try:
        return {k: json.loads(v) for k, v in con.execute("select key, value from config").fetchall()}
    finally:
        con.close()


class UsageNote(unittest.TestCase):
    OWN = "Open WebUI's own speech-to-text"
    OTHER = "an engine outside the stack"

    def notes(self, p: dict) -> str:
        return " | ".join(usage.uncounted(p))

    def test_the_note_stays_until_provisioning_points_open_webui_at_voice_typing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = openwebui_db(tmp)
            p = stt_profile(tmp)
            self.assertIn(self.OWN, self.notes(p))
            changed = media.provision_openwebui(db, services.openwebui_stt_settings(p, KEY))
            # All the rows in one transaction; the request format was multipart already.
            self.assertEqual(changed, ["audio.stt.engine", "audio.stt.model", "audio.stt.openai.api_base_url",
                                       "audio.stt.openai.api_key"])
            rows = config_rows(db)
            self.assertEqual((rows["audio.stt.engine"], rows["audio.stt.openai.api_base_url"], rows["ui.other"]),
                             ("openai", "http://127.0.0.1:8790/v1", "kept"))
            self.assertEqual(len(list(db.parent.glob("webui.db.bak-*"))), 1)
            self.assertNotIn("speech-to-text", self.notes(p))
            self.assertEqual(media.provision_openwebui(db, services.openwebui_stt_settings(p, KEY)), [])

    def test_engines_outside_the_stack_are_named(self):
        for engine, url in (("openai", "https://api.openai.com/v1"), ("openai", "http://127.0.0.1:4000/v1"),
                            ("deepgram", "https://api.openai.com/v1"), ("azure", "")):
            with self.subTest(engine=engine, url=url), tempfile.TemporaryDirectory() as tmp:
                openwebui_db(tmp, engine, url)
                notes = self.notes(stt_profile(tmp))
                self.assertIn(self.OTHER, notes)
                self.assertNotIn(self.OWN, notes)
        with tempfile.TemporaryDirectory() as tmp:
            openwebui_db(tmp, "openai", "http://localhost:8790/v1/")
            self.assertNotIn("speech-to-text", self.notes(stt_profile(tmp)))

    def test_before_the_first_start_the_environment_decides(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertNotIn("speech-to-text", self.notes(stt_profile(tmp)))
            self.assertIn(self.OWN, self.notes(stt_profile(tmp, dictation_on=False)))
            self.assertNotIn("speech-to-text", self.notes(stt_profile(tmp, open_webui_on=False)))


@unittest.skipUnless(importlib.util.find_spec("av") and importlib.util.find_spec("numpy"),
                     "decoding needs PyAV and numpy (the voice typing environment)")
class Decoding(unittest.TestCase):
    def tone(self, seconds: float, fmt: str = "webm", codec: str = "libopus", rate: int = 48000) -> bytes:
        import av
        import numpy as np

        buf = io.BytesIO()
        with av.open(buf, mode="w", format=fmt) as out:
            stream = out.add_stream(codec, rate=rate, layout="mono")
            samples = (0.3 * np.sin(2 * np.pi * 440 * np.arange(int(rate * seconds)) / rate)).astype(np.float32)
            frame = av.AudioFrame.from_ndarray(samples[None, :], format="fltp", layout="mono")
            frame.sample_rate = rate
            for packet in stream.encode(frame):
                out.mux(packet)
            for packet in stream.encode(None):
                out.mux(packet)
        return buf.getvalue()

    def test_formats_decode_to_16khz_mono(self):
        for fmt, codec, rate in (("webm", "libopus", 48000), ("ogg", "libopus", 48000), ("wav", "pcm_s16le", 44100),
                                 ("ipod", "aac", 44100), ("mp3", "libmp3lame", 44100), ("flac", "flac", 44100)):
            with self.subTest(fmt):
                audio = t.decode_audio(self.tone(2.0, fmt, codec, rate))
                self.assertEqual(str(audio.dtype), "float32")
                self.assertAlmostEqual(len(audio) / 16000, 2.0, delta=0.1)

    def test_a_cut_off_recording_gives_what_is_there(self):
        data = self.tone(2.0)
        self.assertGreater(len(t.decode_audio(data[: int(len(data) * 0.6)])), 8000)

    def test_long_audio_is_refused_before_it_fills_the_memory(self):
        data = self.tone(3.0, "flac", "flac", 44100)
        for limit in (1.0, 2.5):  # the container's duration, then the running count (inside the 1 s tolerance)
            with self.subTest(limit=limit), self.assertRaises(t.ApiError) as cm:
                t.decode_audio(data, max_seconds=limit)
            self.assertEqual((cm.exception.status, cm.exception.code), (413, "audio_too_long"))
        self.assertAlmostEqual(len(t.decode_audio(data, max_seconds=3.5)) / 16000, 3.0, delta=0.1)

    def test_files_that_are_not_audio(self):
        import av
        import numpy as np

        buf = io.BytesIO()
        with av.open(buf, mode="w", format="mp4") as out:
            s = out.add_stream("mpeg4", rate=10)
            s.width, s.height, s.pix_fmt = 64, 64, "yuv420p"
            for _ in range(3):
                for packet in s.encode(av.VideoFrame.from_ndarray(np.zeros((64, 64, 3), np.uint8), format="rgb24")):
                    out.mux(packet)
            for packet in s.encode(None):
                out.mux(packet)
        for label, data in (("video only", buf.getvalue()), ("text", b"not audio\n" * 100),
                            ("header only", self.tone(2.0)[:200])):
            with self.subTest(label), self.assertRaises(t.ApiError) as cm:
                t.decode_audio(data)
            self.assertEqual(cm.exception.status, 400)


if __name__ == "__main__":
    unittest.main()
