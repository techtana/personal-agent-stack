"""Tests for the Logseq refine plugin's side in Python: voice typing's /plugin/ routes (stacklib/dictation/pluginapi.py
and control.py), the REFINE_BEARER key, and the build and status helpers (stacklib/logseq_plugin.py). Every refine
log here is a temporary file and every model is a fake; nothing touches the real log, gateway, clipboard, npm or
Logseq.
"""
from __future__ import annotations

import ast
import http.client
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import logseq_plugin  # noqa: E402
from stacklib import dictation  # noqa: E402
from stacklib.dictation import control, pluginapi, refine  # noqa: E402
from stacklib.dictation.refinelog import RefineLog  # noqa: E402

KEY = "test-refine-key"
UUID = "6af021c1-bcc4-498b-9147-e8c9576d5c06"
BLOCK = "this are a first block that mention [[Project Alpha]] and #idea with teh typo"
FIXED = "This is a first block that mentions [[Project Alpha]] and #idea, with the typo fixed."


def fake_refine(replies: dict | None = None, calls: list | None = None, default=None):
    """refine_fn stand-in: answers from `replies` (text -> reply) like refine.refine_text would, recording each call."""
    def fn(text, style, *, model, timeout):
        if calls is not None:
            calls.append({"text": text, "style": style.id, "model": model})
        reply = (replies or {}).get(text, default)
        if reply is None:
            return refine.Result(text, False, "the gateway is not reachable", 0.1)
        if isinstance(reply, refine.Result):
            return reply
        lead, core, trail = refine.split_space(text)
        ok, why = refine.check(core, reply, style)
        if not ok:
            return refine.Result(text, False, why, 0.2, suggestion=reply, served="qwen3.5:9b")
        if refine.same_text(reply, core):
            return refine.Result(text, True, "no changes needed", 0.2, suggestion=reply, unchanged=True)
        return refine.Result(lead + reply + trail, True, "", 0.3, suggestion=reply, served="qwen3.5:9b")
    return fn


def headers(key: str | None = KEY) -> dict:
    return {"Authorization": f"Bearer {key}"} if key is not None else {}


class Markup(unittest.TestCase):
    def test_segments_keep_property_lines_apart_and_join_back(self):
        text = "Title line\nstatus:: draft\ntags:: a, b\nmore text\nand more"
        parts = pluginapi.segments(text)
        self.assertEqual(parts, [(False, "Title line\n"), (True, "status:: draft\ntags:: a, b\n"),
                                 (False, "more text\nand more")])
        self.assertEqual("".join(c for _, c in parts), text)
        self.assertEqual(pluginapi.segments("just one line"), [(False, "just one line")])
        self.assertEqual(pluginapi.segments("key::"), [(True, "key::")])
        self.assertEqual(pluginapi.segments("a::b is not a property"), [(False, "a::b is not a property")])

    def test_markup_counts_what_must_survive(self):
        found = pluginapi.markup("see [[Project Alpha]] and #idea, ((%s)) {{embed [[x]]}} `code [[y]]` "
                                 "https://example.com/a. #[[two words]] ![pic](../assets/p.png) [site](https://e.org)"
                                 % UUID)
        self.assertEqual(set(found), {"[[Project Alpha]]", "#idea", f"(({UUID}))", "{{embed [[x]]}}", "`code [[y]]`",
                                      "https://example.com/a", "#[[two words]]", "![pic](../assets/p.png)",
                                      "[site](https://e.org)"})

    def test_hashes_inside_words_are_not_tags(self):
        self.assertEqual(pluginapi.markup("C# and abc#def and issue#3"), {})
        self.assertEqual(set(pluginapi.markup("#start, then (#inner) #end.")), {"#start", "#inner", "#end"})

    def test_markup_changes(self):
        self.assertEqual(pluginapi.markup_changes(BLOCK, FIXED), "")
        why = pluginapi.markup_changes(BLOCK, FIXED.replace("[[Project Alpha]]", "[[project alpha]]"))
        self.assertIn("[[Project Alpha]]", why)
        self.assertIn("added [[project alpha]]", why)
        self.assertIn("#idea", pluginapi.markup_changes(BLOCK, FIXED.replace("#idea", "idea")))
        two = "[[A]] and [[A]]"
        self.assertTrue(pluginapi.markup_changes(two, "[[A]] only"), "a link written twice must come back twice")
        self.assertEqual(pluginapi.markup_changes("```\ncode\n```", "```\ncode\n```"), "")

    def test_graph_label(self):
        self.assertEqual(pluginapi.graph_label("logseq_db_Notes"), "Notes")
        self.assertEqual(pluginapi.graph_label(" Plain "), "Plain")
        self.assertEqual(pluginapi.graph_label(None), "")


class RefineBlock(unittest.TestCase):
    cfg = refine.Config()
    style = refine.BUILTIN[0]

    def test_one_run(self):
        calls = []
        res = pluginapi.refine_block(BLOCK, self.style, self.cfg, fake_refine({BLOCK: FIXED}, calls))
        self.assertTrue(res.ok, res.note)
        self.assertEqual(res.text, FIXED)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["model"], "local-primary")

    def test_property_lines_are_not_sent_and_come_back_unchanged(self):
        text = "this are the title\nstatus:: draft\nand this are the body"
        calls = []
        replies = {"this are the title\n": "This is the title", "and this are the body": "And this is the body."}
        res = pluginapi.refine_block(text, self.style, self.cfg, fake_refine(replies, calls))
        self.assertTrue(res.ok, res.note)
        self.assertEqual(res.text, "This is the title\nstatus:: draft\nAnd this is the body.")
        self.assertEqual([c["text"] for c in calls], ["this are the title\n", "and this are the body"])

    def test_unchanged(self):
        res = pluginapi.refine_block("All good.", self.style, self.cfg, fake_refine({"All good.": "All good."}))
        self.assertTrue(res.ok and res.unchanged)
        self.assertEqual(res.text, "All good.")

    def test_changed_markup_is_rejected_with_the_whole_block_as_suggestion(self):
        bad = FIXED.replace("#idea", "#Idea")
        text = BLOCK + "\nkey:: v"
        res = pluginapi.refine_block(text, self.style, self.cfg, fake_refine({BLOCK + "\n": bad}))
        self.assertFalse(res.ok)
        self.assertIn("Logseq markup", res.note)
        self.assertEqual(res.text, text, "the block's own text, never the bad suggestion")
        self.assertEqual(res.suggestion, bad + "\nkey:: v")

    def test_a_failed_run_stops_with_no_suggestion(self):
        res = pluginapi.refine_block(BLOCK, self.style, self.cfg, fake_refine({}))
        self.assertFalse(res.ok)
        self.assertEqual(res.suggestion, "")
        self.assertIn("not reachable", res.note)

    def test_a_rejected_reply_keeps_its_suggestion(self):
        q = "can you tell me the capital of france"
        res = pluginapi.refine_block(q, self.style, self.cfg, fake_refine({q: "Sure! The capital of France is Paris."}))
        self.assertFalse(res.ok)
        self.assertIn("answered", res.note)
        self.assertEqual(res.suggestion, "Sure! The capital of France is Paris.")

    def test_all_runs_share_one_deadline(self):
        now = [0.0]
        timeouts = []

        def slow(text, style, *, model, timeout):
            timeouts.append(timeout)
            now[0] += 70.0  # each model call takes 70 s of the block's 120 s
            lead, core, trail = refine.split_space(text)
            return refine.Result(lead + core.capitalize() + trail, True, "", 70.0, suggestion=core.capitalize())

        text = "one\nk:: v\ntwo\nk:: v\nthree"
        res = pluginapi.refine_block(text, self.style, self.cfg, slow, clock=lambda: now[0])
        self.assertFalse(res.ok)
        self.assertIn("did not finish within 120 s", res.note)
        self.assertEqual(timeouts, [120.0, 50.0], "the second call only gets what is left; the third never starts")
        self.assertEqual(pluginapi.text_runs(text), 3)


class Api(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = RefineLog(Path(self.tmp.name) / "refine-log.jsonl")
        self.cfg = refine.Config(prompts={"my-voice": {"name": "My voice", "prompt": "Rewrite in my voice."}})
        self.calls: list = []
        self.replies = {BLOCK: FIXED}
        self.now = [1000.0]
        self.lines: list[str] = []
        self.api = pluginapi.PluginApi(cfg=lambda: self.cfg, refine_fn=fake_refine(self.replies, self.calls),
                                       log=self.log, key=lambda: KEY, logline=self.lines.append,
                                       clock=lambda: self.now[0])

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, route: str, body, key: str | None = KEY) -> tuple[int, dict]:
        raw = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        return self.api.respond(f"plugin/{route}", headers(key), raw)

    def refine(self, **extra) -> dict:
        status, answer = self.post("refine", {"text": BLOCK, "app": "logseq", "block": UUID, "page": "Refine test",
                                              "graph": "logseq_db_Demo", **extra})
        self.assertEqual(status, 200, answer)
        return answer

    # ------------------------------------------------------------ the key

    def test_requests_need_the_refine_key(self):
        self.assertEqual(self.post("styles", {}, key=None)[0], 401)
        status, answer = self.post("styles", {}, key="wrong")
        self.assertEqual(status, 401)
        self.assertIn("REFINE_BEARER", answer["error"])
        self.assertEqual(self.api.respond("plugin/styles", {"authorization": "Basic " + KEY}, b"{}")[0], 401)
        self.assertEqual(self.api.respond("plugin/styles", {"AUTHORIZATION": "bearer " + KEY}, b"{}")[0], 200)

    def test_without_a_key_on_this_machine_every_request_is_refused(self):
        self.api.key = lambda: ""
        status, answer = self.post("styles", {})
        self.assertEqual(status, 503)
        self.assertIn("logseq-plugin", answer["error"])

    def test_bad_bodies_and_paths(self):
        self.assertEqual(self.post("styles", b"not json")[0], 400)
        self.assertEqual(self.post("styles", b"[1, 2]")[0], 400)
        self.assertEqual(self.post("styles", b"\xff\xfe")[0], 400)
        self.assertEqual(self.post("nope", {})[0], 404)
        self.assertEqual(self.post("refine", {"text": 5})[0], 400)
        self.assertEqual(self.post("refine", {"text": "   "})[0], 400)

    # ------------------------------------------------------------ styles and refine

    def test_styles_are_the_refine_buttons_styles(self):
        status, answer = self.post("styles", {})
        self.assertEqual(status, 200)
        ids = [s["id"] for s in answer["styles"]]
        self.assertEqual(ids[:7], [s.id for s in refine.BUILTIN])
        self.assertIn({"id": "my-voice", "name": "My voice"}, answer["styles"])
        self.assertEqual((answer["default"], answer["model"], answer["max_chars"]), ("polish", "local-primary", 10000))

    def test_log_first_then_write(self):
        answer = self.refine()
        self.assertEqual((answer["status"], answer["text"], answer["style"]), ("suggested", FIXED, "polish"))
        self.assertEqual(self.log.entries(), [], "nothing is logged before the plugin commits")
        status, done = self.post("commit", {"token": answer["token"], "write": True})
        self.assertEqual(status, 200, done)
        (entry,) = self.log.entries()
        self.assertEqual(entry["id"], done["id"])
        self.assertEqual((entry["kind"], entry["status"], entry["before"], entry["after"]),
                         ("refine", "replaced", BLOCK, FIXED))
        self.assertEqual((entry["app"], entry["block"], entry["page"], entry["graph"], entry["source"]),
                         ("logseq", UUID, "Refine test", "Demo", "plugin"))
        self.assertEqual(entry["window"], "Refine test - Logseq (Demo)")
        self.assertEqual((entry["style"], entry["style_name"], entry["model"]), ("polish", "Polish", "local-primary"))
        self.assertEqual(self.post("commit", {"token": answer["token"], "write": True})[0], 404, "a token works once")

    def test_a_block_that_changed_meanwhile_is_logged_as_skipped(self):
        answer = self.refine(style="concise")
        status, done = self.post("commit", {"token": answer["token"], "write": False,
                                            "note": "the block changed while the model worked"})
        self.assertEqual((status, done["status"]), (200, "skipped"))
        (entry,) = self.log.entries()
        self.assertEqual((entry["status"], entry["style"], entry["after"]), ("skipped", "concise", FIXED))
        self.assertIn("changed", entry["note"])

    def test_rejected_failed_and_unchanged_are_logged_at_once(self):
        self.replies[BLOCK] = FIXED.replace("[[Project Alpha]]", "[[project alpha]]")
        answer = self.refine()
        self.assertEqual((answer["ok"], answer["status"]), (False, "rejected"))
        self.assertNotIn("token", answer)
        self.replies[BLOCK] = None
        self.assertEqual(self.refine()["status"], "failed")
        self.replies[BLOCK] = BLOCK
        answer = self.refine()
        self.assertEqual((answer["ok"], answer["status"], answer["text"]), (True, "unchanged", BLOCK))
        self.assertEqual([e["status"] for e in self.log.entries()], ["unchanged", "failed", "rejected"])
        rejected = self.log.entries()[2]
        self.assertIn("[[project alpha]]", rejected["after"])
        self.assertIn("Logseq markup", rejected["note"])

    def test_styles_and_limits(self):
        self.assertEqual(self.refine(style="my-voice")["style_name"], "My voice")
        self.assertEqual(self.calls[-1]["style"], "my-voice")
        status, answer = self.post("refine", {"text": BLOCK, "style": "nope"})
        self.assertEqual(status, 400)
        self.assertIn("nope", answer["error"])
        status, answer = self.post("refine", {"text": "x" * (self.cfg.max_chars + 1)})
        self.assertEqual(status, 413)
        self.assertIn("longer than", answer["error"])

    def test_one_refine_at_a_time(self):
        self.api.turn.acquire()
        try:
            with mock.patch.object(pluginapi, "BUSY_WAIT_S", 0.05):
                status, answer = self.post("refine", {"text": BLOCK})
            self.assertEqual(status, 503)
            self.assertIn("another block", answer["error"])
        finally:
            self.api.turn.release()

    def test_a_crash_inside_is_an_answer(self):
        self.api.refine_fn = mock.Mock(side_effect=RuntimeError("boom"))
        status, answer = self.post("refine", {"text": BLOCK})
        self.assertEqual(status, 500)
        self.assertIn("RuntimeError", answer["error"])
        self.assertTrue(any("boom" in line for line in self.lines))

    def test_uncommitted_suggestions_are_logged_as_skipped(self):
        self.refine()
        self.now[0] += pluginapi.PENDING_S + 1
        self.post("styles", {})  # any request sweeps
        (entry,) = self.log.entries()
        self.assertEqual(entry["status"], "skipped")
        self.assertIn("did not ask", entry["note"])
        self.refine()
        self.assertEqual(self.api.flush(), 1)
        self.assertEqual(self.log.entries()[0]["note"], "voice typing stopped before the plugin wrote it")
        self.assertEqual(self.api.pending, {})

    # ------------------------------------------------------------ revert

    def replaced(self) -> str:
        answer = self.refine()
        return self.post("commit", {"token": answer["token"], "write": True})[1]["id"]

    def test_revert_puts_the_original_back_through_the_log(self):
        refine_id = self.replaced()
        status, answer = self.post("revert", {"text": FIXED, "block": UUID, "graph": "logseq_db_Demo", "app": "logseq"})
        self.assertEqual(status, 200, answer)
        self.assertEqual((answer["ok"], answer["text"], answer["entry"], answer["match"]), (True, BLOCK, refine_id, 1.0))
        self.post("commit", {"token": answer["token"], "write": True})
        entry = self.log.entries()[0]
        self.assertEqual((entry["kind"], entry["of"], entry["before"], entry["after"], entry["status"]),
                         ("revert", refine_id, FIXED, BLOCK, "replaced"))
        self.assertEqual(entry["page"], "Refine test", "the page comes from the refine when the plugin sends none")
        again = self.post("revert", {"text": BLOCK, "block": UUID})[1]
        self.assertEqual((again["ok"], again["status"]), (False, "none"), "a reverted refine is not offered again")

    def test_revert_needs_a_matching_block(self):
        self.assertEqual(self.post("revert", {"text": FIXED, "block": UUID})[1]["status"], "none")
        self.replaced()
        changed = self.post("revert", {"text": "Something else entirely, written later.", "block": UUID})[1]
        self.assertEqual((changed["ok"], changed["status"]), (False, "changed"))
        other = self.post("revert", {"text": FIXED, "block": UUID, "graph": "logseq_db_Other"})[1]
        self.assertEqual(other["status"], "none", "a block of another graph with the same uuid is not this one")
        edited = self.post("revert", {"text": FIXED.replace("fixed.", "fixed!"), "block": UUID})[1]
        self.assertTrue(edited["ok"])
        self.assertLess(edited["match"], 1.0)
        self.assertEqual(self.post("revert", {"text": FIXED, "block": "not-a-uuid"})[0], 400)

    def test_skipped_refines_are_not_reverted(self):
        answer = self.refine()
        self.post("commit", {"token": answer["token"], "write": False})
        self.assertEqual(self.post("revert", {"text": BLOCK, "block": UUID})[1]["status"], "none")

    # ------------------------------------------------------------ limits against a misbehaving caller

    def test_a_block_cut_into_many_runs_is_refused_before_the_model(self):
        text = "a\nk:: v\n" * (pluginapi.MAX_RUNS + 1)
        status, answer = self.post("refine", {"text": text})
        self.assertEqual(status, 413)
        self.assertIn("in parts", answer["error"])
        self.assertEqual(self.calls, [])

    def test_waiting_suggestions_are_capped(self):
        with mock.patch.object(pluginapi, "MAX_PENDING", 2):
            self.refine()
            self.refine()
            status, answer = self.post("refine", {"text": BLOCK})
            self.assertEqual(status, 503)
            self.assertIn("waiting", answer["error"])
            self.assertEqual(len(self.calls), 2, "refused before the model ran")
            status, _ = self.post("revert", {"text": FIXED, "block": UUID})
            self.assertEqual(status, 503)

    def test_revert_is_bounded_and_one_at_a_time(self):
        status, answer = self.post("revert", {"text": "x" * (2 * self.cfg.max_chars + 1), "block": UUID})
        self.assertEqual(status, 413)
        self.api.turn.acquire()
        try:
            with mock.patch.object(pluginapi, "BUSY_WAIT_S", 0.05):
                status, answer = self.post("revert", {"text": FIXED, "block": UUID})
            self.assertEqual(status, 503)
        finally:
            self.api.turn.release()

    def test_styles_tell_the_plugin_how_long_to_wait(self):
        self.cfg.timeout_s = 300.0
        self.assertEqual(self.post("styles", {})[1]["timeout_s"], 300.0)

    def test_plugin_entries_stay_out_of_the_app_wide_revert(self):
        from stacklib.dictation.refinelog import revertable_in_app

        self.replaced()
        (entry,) = self.log.entries()
        self.assertFalse(revertable_in_app(entry))
        self.assertIsNone(self.log.find(FIXED), "selecting the text in another app must not find a plugin entry")
        self.assertTrue(revertable_in_app({**entry, "source": ""}))


class Http(unittest.TestCase):
    """The routes through the real control server: Origin and Host rules first, then the plugin API."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = RefineLog(Path(self.tmp.name) / "refine-log.jsonl")
        self.api = pluginapi.PluginApi(cfg=refine.Config, refine_fn=fake_refine({BLOCK: FIXED}), log=self.log,
                                       key=lambda: KEY)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.server = control.ControlServer(self.port, lambda: {"ok": True}, lambda name: {"ok": True},
                                            plugin=self.api)
        self.server.start()

    def tearDown(self):
        self.server.stop()
        self.tmp.cleanup()

    def request(self, path: str, body: dict | None = None, extra: dict | None = None, method: str = "POST"):
        data = json.dumps(body or {}).encode("utf-8") if method == "POST" else None
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/{path}", data=data, method=method,
                                     headers={"Content-Type": "application/json", **headers(), **(extra or {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def test_refine_and_commit_over_http(self):
        status, answer = self.request("plugin/refine", {"text": BLOCK, "block": UUID, "page": "P", "graph": "G"})
        self.assertEqual((status, answer["status"]), (200, "suggested"))
        status, done = self.request("plugin/commit", {"token": answer["token"], "write": True})
        self.assertEqual((status, done["status"]), (200, "replaced"))
        self.assertEqual(self.log.entries()[0]["block"], UUID)

    def test_web_pages_are_still_refused(self):
        status, answer = self.request("plugin/styles", extra={"Origin": "lsp://logseq.io"})
        self.assertEqual(status, 403)
        self.assertIn("web pages", answer["error"])
        self.assertEqual(self.request("plugin/styles", extra={"Host": "evil.example:80"})[0], 403)
        self.assertEqual(self.request("plugin/styles", method="GET")[0], 405)
        self.assertEqual(self.request("plugin/styles", extra={"Authorization": "Bearer nope"})[0], 401)

    def test_body_limits(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.putrequest("POST", "/plugin/styles")
        conn.putheader("Authorization", f"Bearer {KEY}")
        conn.putheader("Content-Length", str(pluginapi.MAX_BODY_BYTES + 1))
        conn.endheaders()
        self.assertEqual(conn.getresponse().status, 413)
        conn.close()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/plugin/styles", body=iter([b"{}"]), headers={"Authorization": f"Bearer {KEY}",
                                                                           "Transfer-Encoding": "chunked"})
        self.assertEqual(conn.getresponse().status, 411)
        conn.close()
        self.assertEqual(control.PLUGIN_MAX_BODY, pluginapi.MAX_BODY_BYTES)
        self.assertEqual(control.PLUGIN_PREFIX, pluginapi.PREFIX)

    def test_without_the_plugin_api(self):
        self.server.stop()
        self.server = control.ControlServer(self.port, lambda: {"ok": True}, lambda name: {"ok": True})
        self.server.start()
        self.assertEqual(self.request("plugin/styles")[0], 503)


class Gateway(unittest.TestCase):
    def test_the_plugins_refines_name_themselves_to_the_gateway(self):
        agents = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                agents.append(self.headers.get("User-Agent"))
                body = json.dumps({"model": "qwen3.5:9b", "choices": [
                    {"finish_reason": "stop", "message": {"content": json.dumps({"text": FIXED})}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            res = refine.refine_text(BLOCK, refine.BUILTIN[0], base_url=f"http://127.0.0.1:{server.server_port}",
                                     api_key="k", model="local-primary", user_agent=pluginapi.USER_AGENT)
        finally:
            server.shutdown()
            server.server_close()
        self.assertTrue(res.ok, res.note)
        self.assertEqual(agents, ["agent-stack-logseq-refine"])


class AppWiring(unittest.TestCase):
    """app.py runs in voice typing's own environment (numpy, Tk, faster-whisper), so it is read here, not imported."""

    def setUp(self):
        self.source = (Path(__file__).resolve().parents[1] / "scripts" / "stacklib" / "dictation" / "app.py").read_text(
            encoding="utf-8")
        tree = ast.parse(self.source)
        app = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
        self.methods = {n.name: n for n in app.body if isinstance(n, ast.FunctionDef)}

    def code(self, name: str) -> str:
        return ast.get_source_segment(self.source, self.methods[name])

    def test_the_control_server_gets_the_plugin_api(self):
        init = self.methods["__init__"]
        servers = [c for c in ast.walk(init) if isinstance(c, ast.Call) and ast.unparse(c.func) == "control.ControlServer"]
        self.assertEqual(len(servers), 1)
        self.assertIn("plugin=self.plugin_api", ast.unparse(servers[0]))
        api = [c for c in ast.walk(init) if isinstance(c, ast.Call) and ast.unparse(c.func) == "pluginapi.PluginApi"]
        self.assertEqual(len(api), 1)
        for keyword in ("cfg=self._refine_cfg", "refine_fn=self._plugin_refine_fn", "log=self.refine_log",
                        "key=refine_key"):
            self.assertIn(keyword, ast.unparse(api[0]))

    def test_the_plugins_refines_use_their_own_user_agent(self):
        self.assertIn("user_agent=pluginapi.USER_AGENT", self.code("_plugin_refine_fn"))
        self.assertNotIn("user_agent", self.code("_refine_fn"), "the refine button keeps agent-stack-refine")

    def test_waiting_suggestions_are_logged_at_shutdown(self):
        run = self.code("run")
        self.assertLess(run.index("self.server.stop()"), run.index("self.plugin_api.flush()"))

    def test_health_says_whether_the_plugin_key_is_set(self):
        self.assertIn('"plugin": {"key": bool(refine_key())', self.code("health"))


class Key(unittest.TestCase):
    def test_ensure_refine_key_appends_once_and_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(dictation.REFINE_KEY_NAME, None)
            env = Path(tmp) / ".env"
            env.write_text("# comment\nOTHER=1", encoding="utf-8")
            key = dictation.ensure_refine_key(env)
            self.assertGreaterEqual(len(key), 32)
            self.assertEqual(env.read_text(encoding="utf-8"), f"# comment\nOTHER=1\nREFINE_BEARER={key}\n")
            self.assertEqual(dictation.ensure_refine_key(env), key)
            self.assertEqual(env.read_text(encoding="utf-8").count("REFINE_BEARER="), 1)


class PluginFolder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.plugin = root / "logseq-refine"
        self.dist = self.plugin / "dist"
        self.home = root / "home" / ".logseq"
        self.home.mkdir(parents=True)
        self.patches = [mock.patch.object(logseq_plugin, "PLUGIN_DIR", self.plugin),
                        mock.patch.object(logseq_plugin, "DIST", self.dist)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def build_dist(self):
        self.dist.mkdir(parents=True)
        for f in ("index.html", "lsplugin.user.js"):
            (self.dist / f).write_text("x", encoding="utf-8")

    def test_status_steps(self):
        with mock.patch("stacklib.dictation.refine_key", return_value=""):
            self.assertEqual(logseq_plugin.status(self.home).state, "Not built")
            self.build_dist()
            self.assertEqual(logseq_plugin.status(self.home).state, "No key")
        with mock.patch("stacklib.dictation.refine_key", return_value=KEY):
            s = logseq_plugin.status(self.home)
            self.assertEqual((s.level, s.state), ("off", "Built"))
            self.assertIn("Load unpacked plugin", s.detail)
            (self.home / "preferences.json").write_text(json.dumps({"externals": [str(self.plugin) + os.sep]}),
                                                        encoding="utf-8")
            self.assertEqual(logseq_plugin.status(self.home).state, "Loaded in Logseq")

    def test_loaded_in_logseq_reads_only_the_plugin_list(self):
        self.assertIsNone(logseq_plugin.loaded_in_logseq(self.home))
        prefs = self.home / "preferences.json"
        prefs.write_text("{broken", encoding="utf-8")
        self.assertFalse(logseq_plugin.loaded_in_logseq(self.home))
        prefs.write_text(json.dumps({"externals": ["C:/elsewhere", 3]}), encoding="utf-8")
        self.assertFalse(logseq_plugin.loaded_in_logseq(self.home))
        before = prefs.read_bytes()
        prefs.write_text(json.dumps({"externals": [str(self.plugin)]}), encoding="utf-8")
        self.assertTrue(logseq_plugin.loaded_in_logseq(self.home))
        self.assertNotEqual(before, prefs.read_bytes())  # (only the test wrote it)

    def test_build_runs_npm_in_the_plugin_folder(self):
        self.plugin.mkdir()
        (self.plugin / "package-lock.json").write_text("{}", encoding="utf-8")
        ran = []

        def fake_run(cmd, **kw):
            ran.append((cmd[1:], kw["cwd"]))
            if cmd[1:3] == ["run", "build"]:
                self.build_dist()
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(logseq_plugin, "which", return_value="npm"), \
                mock.patch.object(logseq_plugin.subprocess, "run", side_effect=fake_run):
            logseq_plugin.build()
        self.assertEqual([r[0][:2] for r in ran], [["ci", "--ignore-scripts"], ["run", "build"]])
        self.assertTrue(all(cwd == self.plugin for _, cwd in ran))

    def test_build_explains_missing_npm_and_failures(self):
        with mock.patch.object(logseq_plugin, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Node.js"):
                logseq_plugin.build()
        self.plugin.mkdir()
        failed = mock.Mock(returncode=1, stdout="", stderr="npm ERR! network down")
        with mock.patch.object(logseq_plugin, "which", return_value="npm"), \
                mock.patch.object(logseq_plugin.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "network down"):
                logseq_plugin.build()

    def test_setup_builds_once_makes_the_key_and_copies_it(self):
        self.build_dist()
        with mock.patch.object(logseq_plugin, "build") as build, \
                mock.patch("stacklib.dictation.ensure_refine_key", return_value=KEY), \
                mock.patch.object(logseq_plugin, "copy_to_clipboard", return_value=7) as copy:
            text, copied = logseq_plugin.setup()
        build.assert_not_called()
        copy.assert_called_once_with(KEY)
        self.assertEqual(copied, 7)
        self.assertIn("kept out of clipboard history", text)

    def test_copy_to_clipboard_elsewhere_uses_the_system_tool(self):
        with mock.patch.object(logseq_plugin, "IS_WINDOWS", False), \
                mock.patch.object(logseq_plugin.shutil, "which", side_effect=lambda n: n if n == "pbcopy" else None), \
                mock.patch.object(logseq_plugin.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            self.assertEqual(logseq_plugin.copy_to_clipboard("abc"), 1)
            self.assertFalse(logseq_plugin.clear_clipboard_if(1))
        self.assertEqual((run.call_args.args[0], run.call_args.kwargs["input"]), (["pbcopy"], b"abc"))
        with mock.patch.object(logseq_plugin, "IS_WINDOWS", False), \
                mock.patch.object(logseq_plugin.shutil, "which", return_value="pbcopy"), \
                mock.patch.object(logseq_plugin.subprocess, "run", side_effect=OSError("no tool")):
            self.assertEqual(logseq_plugin.copy_to_clipboard("abc"), 0)

    @unittest.skipUnless(os.name == "nt", "the Win32 clipboard helper")
    def test_copy_to_clipboard_on_windows_stays_out_of_history_and_is_cleared_later(self):
        from stacklib.dictation import winsys

        board = mock.Mock()
        board.set_text.return_value = 41
        with mock.patch.object(winsys, "Clipboard", return_value=board):
            self.assertEqual(logseq_plugin.copy_to_clipboard("abc"), 41)
            board.set_text.assert_called_once_with("abc", hide=True)
            with mock.patch.object(winsys, "sequence", return_value=42):
                self.assertFalse(logseq_plugin.clear_clipboard_if(41), "something else was copied since")
            board.restore.assert_not_called()
            with mock.patch.object(winsys, "sequence", return_value=41):
                self.assertTrue(logseq_plugin.clear_clipboard_if(41))
            board.restore.assert_called_once_with([])
        with mock.patch.object(winsys, "Clipboard", side_effect=OSError("in use")):
            self.assertEqual(logseq_plugin.copy_to_clipboard("abc"), 0)


if __name__ == "__main__":
    unittest.main()
