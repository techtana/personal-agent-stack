"""Local control endpoint of the voice typing app: the tray's health check and its "Dictate now" menu item, and speech
to text for Open WebUI's microphone.

    GET  /health                    -> {"ok": true, "state": "idle", "engine": "ready", "device": "cuda", ...}
    POST /toggle|start|stop|cancel|show|hide|quit
    POST /reload                    re-read the settings that apply without a restart (the cleanup prompt)
    POST /v1/audio/transcriptions   OpenAI-compatible, with a bearer key (transcriptions.py)

It listens on 127.0.0.1 only. A web page could still aim a request at 127.0.0.1 (cross-site request forgery, or DNS
rebinding with its own host name), so requests with an Origin header or a Host other than this address are refused,
and actions need POST. Local programs are trusted as much as any program that can already press keys; the
transcription endpoint, which runs Whisper on whatever audio it is sent, also wants its own key (DICTATION_BEARER).
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Mapping

from . import transcriptions

ACTIONS = ("toggle", "start", "stop", "cancel", "show", "hide", "quit", "reload")
LINGER_BYTES = 2 * transcriptions.MAX_BODY_BYTES  # what a refused upload may still send before the socket closes
LINGER_S = 10.0


def linger(rfile, sock: socket.socket, max_bytes: int = LINGER_BYTES, max_s: float = LINGER_S) -> None:
    """After the answer, read and drop what the caller is still sending until it closes (or the budget runs out).
    Closing a socket with unread data resets the connection: on Windows the caller then often sees the reset instead
    of the answer (2 of 5 tries with a 3 MB upload answered 401 unread)."""
    deadline = time.monotonic() + max_s
    got = 0
    try:
        sock.settimeout(1.0)
        while got < max_bytes and time.monotonic() < deadline:
            data = rfile.read1(1 << 16)
            if not data:
                return
            got += len(data)
    except OSError:
        pass


def check_request(method: str, path: str, headers: Mapping[str, str], port: int) -> tuple[int, str] | None:
    """None when the request may proceed, else (HTTP status, reason)."""
    lower = {k.lower(): v for k, v in headers.items()}
    if lower.get("origin"):
        return 403, "requests from web pages are refused"
    host = (lower.get("host") or "").strip().lower()
    if host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
        return 403, "unexpected Host header"
    name = path.split("?", 1)[0].strip("/")
    if name == "health":
        return None if method == "GET" else (405, "use GET")
    if name in ACTIONS or name == transcriptions.ROUTE:
        return None if method == "POST" else (405, "use POST")
    return 404, "unknown path"


class _Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second socket bind a port that is in use; without it a second copy of the app
    # fails to bind, which is how it learns that one is already running.
    allow_reuse_address = os.name != "nt"
    daemon_threads = True


class ControlServer:
    """`transcribe` (audio file bytes, language=, prompt=, client=) -> text serves /v1/audio/transcriptions for callers
    with `api_key` (a string, or a function read on each request); without them that path answers 503."""

    def __init__(self, port: int, health: Callable[[], dict], act: Callable[[str], dict],
                 transcribe: transcriptions.Transcriber | None = None, api_key: str | Callable[[], str] = "",
                 log: Callable[[str], None] = lambda m: None) -> None:
        self.port = port
        handler = _handler(port, health, act, transcribe, api_key, log)
        self.httpd = _Server(("127.0.0.1", port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="dictation-control", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def _handler(port: int, health: Callable[[], dict], act: Callable[[str], dict],
             transcribe: transcriptions.Transcriber | None, api_key: str | Callable[[], str],
             log: Callable[[str], None]):
    class Handler(BaseHTTPRequestHandler):
        server_version = "agent-stack-voice-typing"
        timeout = 60  # seconds per socket read or write, so a client that stops sending frees its thread

        def _send(self, status: int, content_type: str, data: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _reply(self, status: int, body: dict) -> None:
            self._send(status, "application/json", json.dumps(body).encode("utf-8"))

        def _answer_upload(self, status: int, content_type: str, data: bytes) -> None:
            try:
                self._send(status, content_type, data)
                self.connection.shutdown(socket.SHUT_WR)  # the answer is complete; the caller may still be sending
            except OSError:
                return  # the caller is gone
            linger(self.rfile, self.connection)

        def _handle(self) -> None:
            name = self.path.split("?", 1)[0].strip("/")
            refused = check_request(self.command, self.path, dict(self.headers.items()), port)
            if refused:
                if name == transcriptions.ROUTE:  # OpenAI's error shape, which Open WebUI shows
                    body = json.dumps(transcriptions.ApiError(*refused).body()).encode("utf-8")
                    self._answer_upload(refused[0], "application/json", body)
                else:
                    self._reply(refused[0], {"ok": False, "error": refused[1]})
                return
            if name == transcriptions.ROUTE:
                self._answer_upload(*transcriptions.respond(self.headers, self.rfile, api_key, transcribe, log))
                return
            try:
                self._reply(200, health() if name == "health" else act(name))
            except Exception as e:  # noqa: BLE001 - report, never kill the server thread
                self._reply(500, {"ok": False, "error": str(e)})

        do_GET = _handle
        do_POST = _handle

        def do_OPTIONS(self) -> None:  # no CORS: a browser's preflight gets no permission
            self._reply(405, {"ok": False, "error": "no cross-origin access"})

        def log_message(self, fmt: str, *args) -> None:  # the tray polls /health every 10 s; keep the log quiet
            pass

    return Handler


def call(port: int, action: str = "health", timeout: float = 3.0) -> dict:
    """Client for stack.py and the tray. Raises OSError when the app is not running."""
    url = f"http://127.0.0.1:{port}/{action}"
    req = urllib.request.Request(url, data=None if action == "health" else b"", method="GET" if action == "health" else "POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except ValueError:
            return {"ok": False, "error": f"HTTP {e.code}"}
