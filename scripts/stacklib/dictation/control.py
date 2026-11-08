"""Local control endpoint of the voice typing app: the tray's health check and its "Dictate now" menu item.

    GET  /health                 -> {"ok": true, "state": "idle", "engine": "ready", "device": "cuda", ...}
    POST /toggle|start|stop|cancel|show|hide|quit
    POST /refine|revert          refine the selection of the window in front (or put its original back), as the hotkey
    POST /show_refine|hide_refine

It listens on 127.0.0.1 only. A web page could still aim a request at 127.0.0.1 (cross-site request forgery, or DNS
rebinding with its own host name), so requests with an Origin header or a Host other than this address are refused,
and actions need POST. Local programs are trusted as much as any program that can already press keys.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Mapping

ACTIONS = ("toggle", "start", "stop", "cancel", "show", "hide", "quit", "refine", "revert", "show_refine",
           "hide_refine")


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
    if name in ACTIONS:
        return None if method == "POST" else (405, "use POST")
    return 404, "unknown path"


class _Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second socket bind a port that is in use; without it a second copy of the app
    # fails to bind, which is how it learns that one is already running.
    allow_reuse_address = os.name != "nt"
    daemon_threads = True


class ControlServer:
    def __init__(self, port: int, health: Callable[[], dict], act: Callable[[str], dict]) -> None:
        self.port = port
        handler = _handler(port, health, act)
        self.httpd = _Server(("127.0.0.1", port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="dictation-control", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def _handler(port: int, health: Callable[[], dict], act: Callable[[str], dict]):
    class Handler(BaseHTTPRequestHandler):
        server_version = "agent-stack-voice-typing"

        def _reply(self, status: int, body: dict) -> None:
            data = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _handle(self) -> None:
            refused = check_request(self.command, self.path, dict(self.headers.items()), port)
            if refused:
                self._reply(refused[0], {"ok": False, "error": refused[1]})
                return
            name = self.path.split("?", 1)[0].strip("/")
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
