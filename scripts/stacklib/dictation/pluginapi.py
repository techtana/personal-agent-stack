"""Refine for app plugins: the Logseq plugin (integrations/logseq-refine) sends a block's text here and writes back what
it gets. Served on voice typing's control port, beside the refine button, so both use the same styles, model and log.

    POST /plugin/styles   {}                                   -> {"styles": [{"id", "name"}], "default", "model", ...}
    POST /plugin/refine   {"text", "style", "app", "block", "page", "graph"}
                          -> {"status": "suggested", "text": <new block text>, "token"} or why not
    POST /plugin/revert   {"text", "block", "graph"}           -> {"text": <the original>, "token", "entry"} or why not
    POST /plugin/commit   {"token", "write": true|false, "note"} -> {"id": <refine log entry>}
    every request:        Authorization: Bearer <REFINE_BEARER>

Log first, then write: a suggestion goes into the refine log (refinelog.py) when the plugin commits it, and the plugin
writes the block only after that answer. So no block changes without a before/after entry; when voice typing stops in
between, the block stays as it was. A suggestion that is never committed is logged as skipped after PENDING_S.
Rejected and failed refines and "no changes needed" are logged at once. Entries carry app "logseq", the page and graph
as the window, and the block's uuid, so History lists them and the plugin's revert finds the newest one for a block.

Logseq markup: lines that look like properties (`key:: value`) are not sent to the model and come back as they were.
Page links, tags, block references, macros, code, images and URLs must come back exactly, as many times as they were
in the text, or the suggestion is rejected (the model's prompt already asks for that; this checks it). The plugin
sends the text as Logseq shows it (`fullTitle`: links and tags by name) and writes back the same form: Logseq 2.0.2
turned a tag written in its stored id form (#[[<uuid>]]) into a new tag named after the uuid.

The key is REFINE_BEARER (.env), its own key: a Logseq plugin's settings are one more place it is stored, and with it
a caller can only refine text and add refine log entries. The control server refuses requests with an Origin header
before they get here; the plugin's requests come from Logseq's main process (logseq.Request), which sends none.
Standard library only.
"""
from __future__ import annotations

import hmac
import json
import re
import secrets
import threading
import time
from collections import Counter
from typing import Callable, Mapping

from .. import usage_log
from . import refine
from .refinelog import MATCH_CHOSEN, RefineLog, similarity

PREFIX = "plugin/"
ROUTES = ("styles", "refine", "revert", "commit")
MAX_BODY_BYTES = 256 * 1024
PENDING_S = 600.0          # a suggestion not committed by then is logged as skipped
MAX_PENDING = 64           # suggestions waiting for a commit; more is a misbehaving caller
MAX_RUNS = 8               # runs of text between property lines in one block, each one model call
BUSY_WAIT_S = 30.0         # for the refine before it, then 503
USER_AGENT = usage_log.user_agent("logseq-refine")  # the Usage tab names it "Refine in Logseq" (usage.COMPONENTS)

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_PROPERTY_LINE = re.compile(r"^[ \t]*[A-Za-z0-9_][\w.-]*::(?:[ \t].*)?$")
# Logseq markup the model must keep, in the order the alternatives are tried at each position: code first, so links
# inside code count once, as part of the code.
_MARKUP = re.compile(
    r"```.*?```"                         # fenced code
    r"|`[^`\n]+`"                        # inline code
    r"|!?\[[^\]\n]*\]\([^)\n]+\)"        # markdown link or image
    r"|#\[\[[^\]\n]+\]\]"                # tag with spaces: #[[two words]]
    r"|\[\[[^\]\n]+\]\]"                 # page link
    r"|\(\([^)\n]+\)\)"                  # block reference
    r"|\{\{[^}\n]+\}\}"                  # macro: embed, query, renderer
    r"|https?://[^\s<>()\[\]]*[^\s<>()\[\].,;:!?'\"]"  # URL, without the sentence's closing punctuation
    r"|(?<![^\s(\[{\"'“‘])#[^\s#,.;:!?()\[\]{}\"'“”‘’]+",  # tag: #word after a space, bracket or quote
    re.S,
)


# ---------------------------------------------------------------- Logseq markup

def segments(text: str) -> list[tuple[bool, str]]:
    """The text cut into runs of whole lines: (True, run) for property lines kept as they are, (False, run) for text
    to refine. Line breaks stay with their lines, so joining the runs gives the text back."""
    out: list[tuple[bool, str]] = []
    for line in text.splitlines(keepends=True):
        kept = bool(_PROPERTY_LINE.match(line.rstrip("\r\n")))
        if out and out[-1][0] == kept:
            out[-1] = (kept, out[-1][1] + line)
        else:
            out.append((kept, line))
    return out


def markup(text: str) -> Counter:
    return Counter(m.group(0) for m in _MARKUP.finditer(text or ""))


def markup_changes(before: str, after: str) -> str:
    """'' when `after` has the same Logseq markup as `before`; otherwise a short note for the bubble and the log."""
    was, now = markup(before), markup(after)
    if was == now:
        return ""
    lost = list((was - now).elements())
    added = list((now - was).elements())
    bits = ([f"dropped or changed {', '.join(lost[:3])}"] if lost else []) + \
           ([f"added {', '.join(added[:3])}"] if added else [])
    return "the model changed Logseq markup (" + "; ".join(bits) + ")"


def text_runs(text: str) -> int:
    return sum(1 for kept, chunk in segments(text) if not kept and chunk.strip())


def refine_block(text: str, style: refine.Style, cfg: refine.Config, refine_fn,
                 clock: Callable[[], float] = time.monotonic) -> refine.Result:
    """Refine each run of text between property lines with `refine_fn` (refine.refine_text's signature) and check its
    markup. One run is one model call; most blocks are one run. All runs together get refine.timeout_s."""
    parts = segments(text)
    done: list[str] = []
    seconds, served, changed = 0.0, "", False
    deadline = clock() + cfg.timeout_s
    for i, (kept, chunk) in enumerate(parts):
        if kept or not chunk.strip():
            done.append(chunk)
            continue
        left = deadline - clock()
        if left < 1.0:
            return refine.Result(text, False, f"the model did not finish within {cfg.timeout_s:g} s", seconds,
                                 served=served)
        res = refine_fn(chunk, style, model=cfg.model, timeout=left)
        seconds += res.seconds
        served = res.served or served
        rest = "".join(c for _, c in parts[i + 1:])
        if not res.ok:
            suggestion = "".join(done) + res.suggestion + rest if res.suggestion else ""
            return refine.Result(text, False, res.note, seconds, suggestion=suggestion, served=served)
        if res.unchanged:
            done.append(chunk)
            continue
        why = markup_changes(chunk, res.text)
        if why:
            return refine.Result(text, False, why, seconds, suggestion="".join(done) + res.text + rest, served=served)
        done.append(res.text)
        changed = True
    after = "".join(done)
    if not changed or refine.same_text(after, text):
        return refine.Result(text, True, "no changes needed", seconds, suggestion=text, unchanged=True, served=served)
    return refine.Result(after, True, "", seconds, suggestion=after, served=served)


def graph_label(name: str) -> str:
    """'logseq_db_Notes' -> 'Notes': database graphs carry a prefix in their name."""
    return str(name or "").strip().removeprefix("logseq_db_")


# ---------------------------------------------------------------- the API

class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status, self.message = status, message


def _text(body: dict, field: str, limit: int, required: bool = False) -> str:
    value = body.get(field, "")
    if not isinstance(value, str):
        raise ApiError(400, f"{field} must be text")
    if required and not value.strip():
        raise ApiError(400, f"{field} is empty")
    if len(value) > limit:
        raise ApiError(413, f"{field} is longer than {limit:,} characters")
    return value


class PluginApi:
    """`cfg()` -> refine.Config, re-read on each call (styles added to the machine file apply at once);
    `refine_fn(text, style, model=, timeout=)` -> refine.Result; `key()` -> REFINE_BEARER ('' = not set)."""

    def __init__(self, *, cfg: Callable[[], refine.Config], refine_fn, log: RefineLog, key: Callable[[], str],
                 logline: Callable[[str], None] = lambda m: None, clock: Callable[[], float] = time.monotonic) -> None:
        self.cfg, self.refine_fn, self.log, self.key, self.logline, self.clock = cfg, refine_fn, log, key, logline, clock
        self.pending: dict[str, tuple[float, dict]] = {}
        self.lock = threading.Lock()
        self.turn = threading.BoundedSemaphore(1)  # one refine at a time; the model runs one request anyway

    # ------------------------------------------------------------ entry point (control.py)

    def respond(self, name: str, headers: Mapping[str, str], body: bytes) -> tuple[int, dict]:
        """(HTTP status, JSON answer) for POST /plugin/<route>. Never raises."""
        route = name.removeprefix(PREFIX)
        try:
            self._authorise(headers)
            if route not in ROUTES:
                raise ApiError(404, "unknown path")
            try:
                data = json.loads(body.decode("utf-8") or "{}")
            except (UnicodeDecodeError, ValueError):
                raise ApiError(400, "the body is not JSON") from None
            if not isinstance(data, dict):
                raise ApiError(400, "the body must be a JSON object")
            self.sweep()
            return 200, getattr(self, f"route_{route}")(data)
        except ApiError as e:
            return e.status, {"ok": False, "error": e.message}
        except Exception as e:  # noqa: BLE001 - answer, never kill the server thread
            self.logline(f"[plugin] {route} failed: {type(e).__name__}: {e}")
            return 500, {"ok": False, "error": f"voice typing failed: {type(e).__name__}"}

    def _authorise(self, headers: Mapping[str, str]) -> None:
        key = self.key() if callable(self.key) else str(self.key or "")
        if not key:
            raise ApiError(503, "voice typing has no REFINE_BEARER to check plugins with; run "
                                "`uv run scripts/stack.py logseq-plugin`")
        lower = {k.lower(): v for k, v in headers.items()}
        scheme, _, given = (lower.get("authorization") or "").partition(" ")
        if scheme.lower() != "bearer" or not given.strip():
            raise ApiError(401, "send the refine key as Authorization: Bearer <REFINE_BEARER>")
        if not hmac.compare_digest(given.strip().encode("utf-8"), key.encode("utf-8")):
            raise ApiError(401, "the key is not this stack's REFINE_BEARER")

    # ------------------------------------------------------------ routes

    def route_styles(self, data: dict) -> dict:
        cfg = self.cfg()
        return {"ok": True, "styles": [{"id": s.id, "name": s.name} for s in refine.styles(cfg)],
                "default": cfg.default, "model": cfg.model, "max_chars": cfg.max_chars, "timeout_s": cfg.timeout_s}

    def route_refine(self, data: dict) -> dict:
        cfg = self.cfg()
        text = _text(data, "text", cfg.max_chars, required=True)
        sid = _text(data, "style", 80).strip()
        if sid and sid not in {s.id for s in refine.styles(cfg)}:
            raise ApiError(400, f"no style {sid!r}; the styles are in refine.prompts of the machine file")
        style = refine.style_named(cfg, sid or None)
        where = self._where(data)
        if text_runs(text) > MAX_RUNS:
            raise ApiError(413, f"the block has more than {MAX_RUNS} stretches of text between property lines; "
                                "refine it in parts")
        self._room()
        if not self.turn.acquire(timeout=BUSY_WAIT_S):
            raise ApiError(503, "still refining another block; try again in a moment")
        try:
            res = refine_block(text, style, cfg, self.refine_fn)
        finally:
            self.turn.release()
        entry = {"kind": "refine", "style": style.id, "style_name": style.name, "model": cfg.model,
                 "served": res.served, **where, "before": text,
                 "after": res.text if res.ok and not res.unchanged else res.suggestion, "seconds": round(res.seconds, 2)}
        sizes = f"{len(text)} -> {len(res.suggestion)} chars in {res.seconds:.2f} s"
        answer = {"style": style.id, "style_name": style.name, "seconds": round(res.seconds, 2)}
        if not res.ok:
            status = "rejected" if res.suggestion else "failed"
            logged = self.log.append({**entry, "status": status, "note": res.note})
            self.logline(f"[plugin] {style.id}: {status}, {res.note} ({sizes})")
            return {"ok": False, "status": status, "error": res.note, "id": logged["id"], **answer}
        if res.unchanged:
            logged = self.log.append({**entry, "status": "unchanged", "note": res.note})
            self.logline(f"[plugin] {style.id}: unchanged ({sizes})")
            return {"ok": True, "status": "unchanged", "text": text, "id": logged["id"], **answer}
        token = self._hold(entry)
        self.logline(f"[plugin] {style.id}: suggested ({sizes})")
        return {"ok": True, "status": "suggested", "text": res.text, "token": token, **answer}

    def route_revert(self, data: dict) -> dict:
        cfg = self.cfg()
        text = _text(data, "text", 2 * cfg.max_chars)  # a refine may have made the block longer
        block = _text(data, "block", 64).strip()
        if not _UUID.match(block):
            raise ApiError(400, "block must be the block's uuid")
        graph = graph_label(_text(data, "graph", 300))
        self._room()
        if not self.turn.acquire(timeout=BUSY_WAIT_S):  # the comparison below is pure Python; one at a time
            raise ApiError(503, "still busy with another block; try again in a moment")
        try:
            return self._revert(text, block, graph, data)
        finally:
            self.turn.release()

    def _revert(self, text: str, block: str, graph: str, data: dict) -> dict:
        entries = self.log.entries(5000)
        reverted = self.log.reverted_ids(entries)
        found = next((e for e in entries if e.get("kind") == "refine" and e.get("block") == block
                      and e.get("status") == "replaced" and (not graph or not e.get("graph") or e.get("graph") == graph)
                      and e.get("id") not in reverted), None)
        if found is None:
            return {"ok": False, "status": "none", "error": "this block has no refine to undo in the refine history"}
        score = similarity(text, found.get("after") or "")
        if score < MATCH_CHOSEN:
            return {"ok": False, "status": "changed", "entry": found.get("id"),
                    "error": "the block has changed too much since it was refined; History has the original to copy"}
        where = self._where({**data, "page": data.get("page") or found.get("page") or ""})
        entry = {"kind": "revert", "of": found.get("id"), "style": found.get("style"),
                 "style_name": found.get("style_name"), **where, "before": text, "after": found.get("before") or "",
                 "match": round(score, 3)}
        token = self._hold(entry)
        return {"ok": True, "status": "found", "text": entry["after"], "token": token, "entry": found.get("id"),
                "when": found.get("time"), "style_name": found.get("style_name"), "match": round(score, 3)}

    def route_commit(self, data: dict) -> dict:
        token = _text(data, "token", 100).strip()
        write = data.get("write")
        if not isinstance(write, bool):
            raise ApiError(400, "write must be true or false")
        note = _text(data, "note", 500).strip()
        with self.lock:
            held = self.pending.pop(token, None)
        if held is None:
            raise ApiError(404, "unknown or expired suggestion; refine the block again")
        entry = {**held[1], "status": "replaced" if write else "skipped", "note": "" if write else note}
        logged = self.log.append(entry)
        self.logline(f"[plugin] {entry['kind']} {logged['id']}: {entry['status']}")
        return {"ok": True, "id": logged["id"], "status": entry["status"]}

    # ------------------------------------------------------------ helpers

    def _where(self, data: dict) -> dict:
        app = (_text(data, "app", 40).strip() or "logseq").lower()
        block = _text(data, "block", 64).strip()
        page = " ".join(_text(data, "page", 300).split())
        graph = graph_label(_text(data, "graph", 300))
        window = " - ".join(b for b in (page, f"{app.capitalize()} ({graph})" if graph else app.capitalize()) if b)
        out = {"app": app, "window": window, "source": "plugin"}
        if _UUID.match(block):
            out["block"] = block
        if page:
            out["page"] = page
        if graph:
            out["graph"] = graph
        return out

    def _room(self) -> None:
        if len(self.pending) >= MAX_PENDING:
            raise ApiError(503, f"{MAX_PENDING} suggestions are waiting for the plugin already; try again later")

    def _hold(self, entry: dict) -> str:
        token = secrets.token_urlsafe(16)
        with self.lock:
            if len(self.pending) >= MAX_PENDING:
                raise ApiError(503, f"{MAX_PENDING} suggestions are waiting for the plugin already; try again later")
            self.pending[token] = (self.clock(), entry)
        return token

    def sweep(self) -> int:
        """Log suggestions the plugin never committed (Logseq closed, the plugin stopped) as skipped."""
        now = self.clock()
        with self.lock:
            old = [t for t, (at, _) in self.pending.items() if now - at > PENDING_S]
            stale = [self.pending.pop(t)[1] for t in old]
        for entry in stale:
            self.log.append({**entry, "status": "skipped", "note": "the plugin did not ask to write it"})
        return len(stale)

    def flush(self) -> int:
        """At shutdown: log every suggestion still waiting, as skipped."""
        with self.lock:
            stale = [e for _, e in self.pending.values()]
            self.pending.clear()
        for entry in stale:
            self.log.append({**entry, "status": "skipped", "note": "voice typing stopped before the plugin wrote it"})
        return len(stale)
