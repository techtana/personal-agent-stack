"""Tests for refining selected text (scripts/stacklib/dictation: refine, refinelog, selection, refiner): the styles and
the request, the checks on the model's reply (against a local fake gateway), the refine log and revert matching, the
clipboard capture and replace rules (against a fake app window and clipboard), the whole flow with fakes, and the
settings. Nothing here touches the real clipboard, keyboard or gateway.
"""
from __future__ import annotations

import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import profile as prof  # noqa: E402
from stacklib import settings  # noqa: E402
from stacklib.dictation import cleanup, control, hotkey, refine, selection  # noqa: E402
from stacklib.dictation.refinelog import RefineLog, similarity  # noqa: E402
from stacklib.dictation.refiner import Refiner  # noqa: E402

TEXT = "hey team, the the release is delayed untill thursday because we found a bug in the payment flow."
FIXED = "Hey team, the release is delayed until Thursday because we found a bug in the payment flow."


class _FakeGateway:
    """A stand-in for LiteLLM's /v1/chat/completions: records requests, answers with a canned reply."""

    def __init__(self, content: str, status: int = 200, finish: str = "stop") -> None:
        self.requests: list[dict] = []
        gw = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                gw.requests.append({"path": self.path, "agent": self.headers.get("User-Agent"), "body": body})
                data = json.dumps({"model": "qwen3.5:9b", "choices": [
                    {"message": {"role": "assistant", "content": content}, "finish_reason": finish}]}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def ask(text: str, reply: str, style: str = "polish", status: int = 200, finish: str = "stop"):
    gw = _FakeGateway(json.dumps({"text": reply}) if reply is not None else "not json", status, finish)
    try:
        res = refine.refine_text(text, refine.style_named(refine.Config(), style), base_url=gw.url, api_key="sk-test",
                                 model="local-primary", timeout=10)
    finally:
        gw.close()
    return res, gw.requests


class Styles(unittest.TestCase):
    def test_builtin_styles(self):
        ids = [s.id for s in refine.BUILTIN]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "polish")
        for s in refine.BUILTIN:
            self.assertTrue(s.name and s.task and s.builtin, s.id)
            self.assertLess(s.min_ratio, 1.0)
            self.assertGreater(s.max_ratio, 1.0)

    def test_your_own_styles(self):
        warnings: list[str] = []
        cfg = refine.Config(prompts={
            "my-voice": "Rewrite in my voice.\n  Short sentences.",
            "email": {"name": "Email reply", "prompt": "Turn notes into an email."},
            "polish": "Polish it, British spelling.",
            "broken": 42,
            "empty": "",
        })
        styles = {s.id: s for s in refine.styles(cfg, warn=warnings.append)}
        self.assertEqual(styles["my-voice"].name, "My voice")
        self.assertEqual(styles["my-voice"].task, "Rewrite in my voice. Short sentences.")
        self.assertFalse(styles["my-voice"].builtin)
        self.assertEqual(styles["email"].name, "Email reply")
        self.assertEqual(styles["polish"].task, "Polish it, British spelling.")       # replaced instructions
        self.assertEqual(styles["polish"].name, "Polish")                             # kept name and limits
        self.assertEqual(styles["polish"].max_ratio, refine.BUILTIN[0].max_ratio)
        self.assertNotIn("broken", styles)
        self.assertNotIn("empty", styles)
        self.assertEqual(len(warnings), 2)
        self.assertEqual([s.id for s in refine.styles(cfg)][:len(refine.BUILTIN)], [s.id for s in refine.BUILTIN])

    def test_style_named_falls_back_to_polish(self):
        cfg = refine.Config(default="concise")
        self.assertEqual(refine.style_named(cfg, None).id, "concise")
        self.assertEqual(refine.style_named(cfg, "bullets").id, "bullets")
        self.assertEqual(refine.style_named(cfg, "nope").id, "polish")


class Configuration(unittest.TestCase):
    def test_defaults_and_overrides(self):
        cfg = refine.Config.from_profile({"refine": {"max_chars": "5000", "button": "off", "timeout_s": "30",
                                                     "default": "grammar"}})
        self.assertEqual((cfg.max_chars, cfg.button, cfg.timeout_s, cfg.default), (5000, False, 30.0, "grammar"))
        self.assertEqual(refine.Config.from_profile({}).hotkey, "ctrl+alt+r")
        self.assertEqual(refine.Config.from_profile({}).menu_hotkey, "ctrl+alt+shift+r")
        self.assertEqual(refine.Config.from_profile({"refine": {"menu_hotkey": ""}}).menu_hotkey, "")

    def test_keep_minutes(self):
        self.assertEqual(refine.Config.from_profile({}).keep_minutes, 30.0)
        self.assertEqual(refine.Config.from_profile({"refine": {"keep_minutes": "15"}}).keep_minutes, 15.0)
        self.assertEqual(refine.Config.from_profile({"refine": {"keep_minutes": 0}}).keep_minutes, 1.0)
        self.assertEqual(refine.Config.from_profile({"refine": {"keep_minutes": 99999}}).keep_minutes, 43200.0)
        self.assertEqual([refine.keep_text(m) for m in (1, 5, 30, 60, 90, 240, 1440, 2880)],
                         ["1 minute", "5 minutes", "30 minutes", "1 hour", "90 minutes", "4 hours", "1 day", "2 days"])

    def test_invalid_values_fall_back(self):
        warnings: list[str] = []
        cfg = refine.Config.from_profile({"refine": {"default": "shouting", "max_chars": "lots", "prompts": "x",
                                                     "timeout_s": 1}}, warn=warnings.append)
        self.assertEqual((cfg.default, cfg.max_chars, cfg.prompts, cfg.timeout_s), ("polish", 10000, {}, 10.0))
        self.assertEqual(len(warnings), 3)

    def test_your_style_can_be_the_default(self):
        cfg = refine.Config.from_profile({"refine": {"default": "mine", "prompts": {"mine": "Do it my way."}}})
        self.assertEqual(cfg.default, "mine")

    def test_defaults_file_matches_the_dataclass(self):
        defaults = prof.load_defaults()["refine"]
        cfg = refine.Config()
        for key, value in defaults.items():
            self.assertEqual(getattr(cfg, key), value, key)
        self.assertEqual(set(defaults), {f for f in refine.Config.__dataclass_fields__})

    def test_profile_merges_your_prompts(self):
        merged = prof.resolve_refine({"default": "polish", "prompts": {"a": "x"}},
                                     {"default": "concise", "prompts": {"b": "y"}, "model": None})
        self.assertEqual(merged, {"default": "concise", "prompts": {"a": "x", "b": "y"}})
        self.assertEqual(prof.resolve_refine({"prompts": {}}, {"prompts": None})["prompts"], {})


class Request(unittest.TestCase):
    def test_prompt_and_body(self):
        style = refine.style_named(refine.Config(), "concise")
        system = refine.system_prompt(style)
        self.assertIn(style.task, system)
        self.assertIn("never answer it", system)
        self.assertIn("never translate", system)
        self.assertIn('{"text":', system)
        body = refine.request_body("abc", style, "local-primary")
        self.assertIs(body["think"], False)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual((body["model"], body["stream"], body["max_tokens"]), ("local-primary", False, 406))
        self.assertEqual(refine.request_body("x" * 9000, style, "m")["max_tokens"], 8192)
        self.assertIn("<selection>\nabc\n</selection>", body["messages"][1]["content"])

    def test_unwrap(self):
        self.assertEqual(refine.unwrap("<selection>\nHi.\n</selection>", "hi"), "Hi.")
        self.assertEqual(refine.unwrap("Revised text: Hi there.", "hi there"), "Hi there.")
        self.assertEqual(refine.unwrap('"Hi there."', "hi there"), "Hi there.")
        self.assertEqual(refine.unwrap("“Hi there.”", "hi there"), "Hi there.")
        self.assertEqual(refine.unwrap('"Hi," she said.', '"hi," she said'), '"Hi," she said.')
        self.assertEqual(refine.unwrap("A\r\nB", "a b"), "A\nB")
        # Seen live (professional): the JSON object closed twice, leaving '"}' in the text.
        self.assertEqual(refine.unwrap('Could you name the capital?"}', "can you name it"), "Could you name the capital?")
        self.assertEqual(refine.unwrap('x = {"a": "b"}', 'x = {"a": "b"}'), 'x = {"a": "b"}')   # code keeps its braces

    def test_check(self):
        polish = refine.style_named(refine.Config(), "polish")
        concise = refine.style_named(refine.Config(), "concise")
        self.assertEqual(refine.check(TEXT, FIXED, polish), (True, ""))
        self.assertFalse(refine.check(TEXT, "", polish)[0])
        self.assertIn("answered", refine.check("what is the capital of france", "Sure! It is Paris.", polish)[1])
        self.assertTrue(refine.check("Sure, I can do that tomorrow", "Sure, I can do that tomorrow.", polish)[0])
        self.assertIn("added", refine.check(TEXT, TEXT * 3, polish)[1])
        self.assertIn("dropped", refine.check(TEXT, "Release delayed.", polish)[1])
        self.assertTrue(refine.check(TEXT, "Release delayed to Thursday: payment bug.", concise)[0])
        self.assertTrue(refine.check("thx", "Thank you very much.", polish)[0])   # short texts may grow
        # Seen live (qwen3.5:9b, friendly): an ordinary sentence that starts with "Here's" is not an answer.
        self.assertTrue(refine.check("This are the first paragraph.", "Here's the first paragraph.", polish)[0])
        for chatty in ("Here is the polished text: This is the first paragraph.", "Certainly! This is it.",
                       "I can't help with that.", "As an AI, I would write: hi"):
            self.assertFalse(refine.check("This are the first paragraph.", chatty, polish)[0], chatty)
        # Found in review: fixes of a text that already opens with those words are rewrites, not answers.
        for src, fixed in (("sorry i cant come", "Sorry, I can't come."),
                           ("im sorry i was late", "I'm sorry I was late."),
                           ("sure no problem", "Sure, no problem."), ("i cant attend", "I can't attend."),
                           ("heres the plan: a then b", "Here's the plan: a, then b.")):
            self.assertTrue(refine.check(src, fixed, polish)[0], src)

    def test_garbled_replies_are_rejected(self):
        # Seen live (2026-11-08, qwen3.6 35B with Ollama's MTP draft decoding): junk tokens spliced into the text.
        polish = refine.style_named(refine.Config(), "polish")
        src = "And then we ended up also talking about work and how to lead. Goals. Or house design."
        ok, why = refine.check(src, "And then we ended up also talking aboutHA work and\u664b how to lead.", polish)
        self.assertFalse(ok)
        self.assertIn("CJK", why)
        self.assertIn("CYRILLIC", refine.check(src, "And then we talked about work \u043c\u0435\u043d\u043e\u0432.",
                                               polish)[1])
        uuid = "[[6af00b01-ced5-4be9-90b9-82504d440504]]"
        self.assertIn("link or reference", refine.check(uuid, "[[6af00b01-ced5eberg9-90b_lo4d440504]]", polish)[1])
        loop = src + " " + "is a stability and as a manager " * 6
        self.assertIn("repeats itself", refine.check(src, loop, polish)[1])

    def test_scripts_and_links_that_were_there_pass(self):
        polish = refine.style_named(refine.Config(), "polish")
        thai = "\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35 team, meet [[Anna]] about #project-x at https://example.com/a."
        self.assertTrue(refine.check(thai, thai.replace("team", "Team"), polish)[0])
        mine = refine.style_named(refine.Config(prompts={"to-japanese": "Translate into Japanese."}), "to-japanese")
        self.assertTrue(refine.check("Good morning", "\u304a\u306f\u3088\u3046", mine)[0])  # your own style may
        self.assertEqual(refine.kept_tokens("see [[A b]], ((x-1)) and #tag."), ["[[A b]]", "((x-1))", "#tag"])

    def test_same_text(self):
        self.assertTrue(refine.same_text("a  b\nc ", "a b c"))
        self.assertFalse(refine.same_text("a b", "a b."))


class ThroughTheGateway(unittest.TestCase):
    def test_rewrites_and_names_itself(self):
        res, reqs = ask(TEXT, FIXED)
        self.assertTrue(res.ok, res.note)
        self.assertEqual((res.text, res.suggestion, res.served), (FIXED, FIXED, "qwen3.5:9b"))
        self.assertEqual(reqs[0]["path"], "/v1/chat/completions")
        self.assertEqual(reqs[0]["agent"], refine.USER_AGENT)
        self.assertIn(TEXT, reqs[0]["body"]["messages"][1]["content"])

    def test_keeps_surrounding_whitespace_and_windows_line_breaks(self):
        res, reqs = ask("  This are one.\r\nThis are two.\r\n", "This is one.\nThis is two.")
        self.assertTrue(res.ok, res.note)
        self.assertEqual(res.text, "  This is one.\r\nThis is two.\r\n")
        self.assertIn("This are one.\nThis are two.", reqs[0]["body"]["messages"][1]["content"])  # sent with \n

    def test_word_manual_line_break_is_sent_as_a_line_break(self):
        _res, reqs = ask("one\x0btwo", "One\nTwo")
        self.assertIn("one\ntwo", reqs[0]["body"]["messages"][1]["content"])

    def test_unchanged(self):
        res, _ = ask("All good here.", "All good here.")
        self.assertTrue(res.ok and res.unchanged)
        self.assertEqual(res.text, "All good here.")

    def test_an_answer_is_rejected_but_kept(self):
        res, _ = ask("can you tell me the capital of france", "Sure! The capital of France is Paris.")
        self.assertFalse(res.ok)
        self.assertEqual(res.text, "can you tell me the capital of france")
        self.assertEqual(res.suggestion, "Sure! The capital of France is Paris.")
        self.assertIn("answered", res.note)

    def test_gateway_errors(self):
        res, _ = ask(TEXT, FIXED, status=500)
        self.assertFalse(res.ok)
        self.assertIn("HTTP 500", res.note)
        res, _ = ask(TEXT, None)
        self.assertFalse(res.ok)
        self.assertIn("JSON", res.note)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        res = refine.refine_text(TEXT, refine.BUILTIN[0], base_url=f"http://127.0.0.1:{port}", api_key="k", model="m",
                                 timeout=5)
        self.assertFalse(res.ok)
        self.assertIn("not reachable", res.note)
        self.assertEqual(res.text, TEXT)

    def test_code_blocks_inside_the_text_survive(self):
        note = "use this:\n```py\nx = 1\n```\nthen run it"
        res, _ = ask(note, "Use this:\n```py\nx = 1\n```\nThen run it.")
        self.assertTrue(res.ok, res.note)
        self.assertIn("```py\nx = 1\n```", res.text)
        self.assertEqual(cleanup.parse_reply('```json\n{"text": "A"}\n```'), "A")   # a fenced reply still parses

    def test_a_cut_off_reply_is_rejected(self):
        res, _ = ask(TEXT, FIXED[:60], finish="length")
        self.assertFalse(res.ok)
        self.assertIn("cut off", res.note)

    def test_whitespace_only(self):
        res = refine.refine_text("  \n ", refine.BUILTIN[0], base_url="http://127.0.0.1:9", api_key="k", model="m")
        self.assertFalse(res.ok)


class Log(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = RefineLog(Path(self.tmp.name) / "sub" / "refine-log.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, before, after, status="replaced", kind="refine", **extra):
        return self.log.append({"kind": kind, "before": before, "after": after, "status": status, **extra})

    def test_append_and_read(self):
        self.assertEqual(self.log.entries(), [])
        a = self.add("one", "One.")
        b = self.add("two", "Two.", status="rejected")
        self.assertRegex(a["id"], r"^\d{8}-\d{6}-[0-9a-f]{4}$")
        self.assertIn("T", a["time"])
        with open(self.log.path, "a", encoding="utf-8") as f:
            f.write("{not json\n\n")
        entries = self.log.entries()
        self.assertEqual([e["id"] for e in entries], [b["id"], a["id"]])   # newest first, broken line skipped
        self.assertEqual(self.log.entries(limit=1)[0]["id"], b["id"])
        self.assertEqual(self.log.get(a["id"])["before"], "one")
        self.assertIn("“quotes” and ไทย", json.dumps(self.add("“quotes” and ไทย", "x"), ensure_ascii=False))

    def test_find(self):
        a = self.add(TEXT, FIXED)
        self.add("draft", "Rejected suggestion.", status="rejected")
        self.add(FIXED, TEXT, kind="revert", of=a["id"])
        self.assertEqual(self.log.find("  " + FIXED.replace(" ", "\n", 2) + "\r\n")[0]["id"], a["id"])  # whitespace
        edited = FIXED.replace("Thursday", "Friday")
        self.assertIsNone(self.log.find(edited, threshold=0.99))
        self.assertEqual(self.log.find(edited)[0]["id"], a["id"])          # close enough
        self.assertIsNone(self.log.find("Rejected suggestion."))          # never reached the document
        self.assertIsNone(self.log.find("Something else entirely."))
        self.assertEqual(self.log.reverted_ids(), {a["id"]})

    def test_entries_expire_after_keep_minutes(self):
        now = [1_800_000_000.0]
        log = RefineLog(Path(self.tmp.name) / "timed.jsonl", keep_minutes=30, clock=lambda: now[0])
        a = log.append({"kind": "refine", "before": TEXT, "after": FIXED, "status": "replaced"})
        self.assertEqual((a["ts"], [e["id"] for e in log.entries()]), (now[0], [a["id"]]))
        now[0] += 29 * 60
        self.assertEqual(log.find(FIXED)[0]["id"], a["id"])          # still kept: revert works
        now[0] += 2 * 60                                              # 31 minutes old
        self.assertEqual((log.entries(), log.find(FIXED), log.get(a["id"])), ([], None, None))
        self.assertTrue(log.path.exists())                           # hidden at once, deleted by the next prune
        self.assertEqual(log.prune(), 1)
        self.assertFalse(log.path.exists())                          # nothing left: the file goes too
        self.assertEqual(log.prune(), 0)

    def test_prune_keeps_fresh_entries_and_drops_broken_lines(self):
        now = [1_800_000_000.0]
        log = RefineLog(Path(self.tmp.name) / "timed.jsonl", keep_minutes=30, clock=lambda: now[0])
        old = log.append({"kind": "refine", "before": "old text", "after": "Old text.", "status": "replaced"})
        now[0] += 20 * 60
        new = log.append({"kind": "refine", "before": "new text", "after": "New text.", "status": "replaced"})
        with open(log.path, "a", encoding="utf-8") as f:
            f.write("{half a line\n")
        now[0] += 15 * 60                                             # old is 35 minutes old, new 15
        self.assertEqual(log.prune(), 2)                              # the old entry and the broken line
        text = log.path.read_text(encoding="utf-8")
        self.assertNotIn("old text", text)
        self.assertIn("new text", text)
        self.assertEqual([e["id"] for e in log.entries()], [new["id"]])
        self.assertNotEqual(old["id"], new["id"])

    def test_append_prunes_and_a_shorter_window_applies_at_once(self):
        now = [1_800_000_000.0]
        log = RefineLog(Path(self.tmp.name) / "timed.jsonl", keep_minutes=30, clock=lambda: now[0])
        log.append({"kind": "refine", "before": "first", "after": "First.", "status": "replaced"})
        now[0] += 40 * 60
        log.append({"kind": "refine", "before": "second", "after": "Second.", "status": "replaced"})
        self.assertNotIn("first", log.path.read_text(encoding="utf-8"))   # gone before the new line was written
        now[0] += 10 * 60
        log.keep_minutes = 5                                           # the tray lowered refine.keep_minutes
        self.assertEqual(log.entries(), [])
        self.assertEqual(log.prune(), 1)

    def test_entries_without_a_readable_time_are_dropped(self):
        log = RefineLog(Path(self.tmp.name) / "timed.jsonl", keep_minutes=30)
        log.path.write_text(json.dumps({"id": "x", "before": "no time"}) + "\n" +
                            json.dumps({"id": "y", "time": "2026-11-07T14:22:33-07:00", "before": "an old one"}) + "\n",
                            encoding="utf-8")
        self.assertEqual(log.entries(), [])
        self.assertEqual(log.prune(), 2)
        self.assertFalse(log.path.exists())

    def test_a_leftover_temp_file_is_removed(self):
        log = RefineLog(Path(self.tmp.name) / "timed.jsonl")
        tmp = log.path.with_name(log.path.name + ".tmp")
        tmp.write_text('{"id": "z", "before": "text from an interrupted prune"}\n', encoding="utf-8")
        log.prune()
        self.assertFalse(tmp.exists())

    def test_similarity(self):
        self.assertEqual(similarity("a b", " a\nb "), 1.0)
        self.assertEqual(similarity("short", "a much much longer text than that"), 0.0)
        self.assertEqual(similarity("", "x"), 0.0)


# ---------------------------------------------------------------- clipboard flow against a fake app

class FakeWin:
    """winsys stand-in: window 100 is the app, with `selected` text; Ctrl+C copies it, Ctrl+V replaces it."""
    SHIFT_INSERT_APPS = {"mintty.exe"}

    def __init__(self, selected: str = TEXT, app: str = "winword.exe", html: str = "", custom: str = "") -> None:
        self.target, self.fg = 100, 100
        self.document = selected
        self.selected = selected
        self.app, self.html, self.custom = app, html, custom
        self.elevated_target: bool | None = False
        self.modifiers_held = False
        self.seq = 1
        self.board = {"text": "what you copied earlier"}
        self.copies = 0
        self.pastes: list[str] = []
        self.on_copy = None
        self.after_copy = None
        self.refuse_activation = False
        self.copy_keys: list[str] = []
        self.activations = 0

    def wait_modifiers_released(self, timeout):
        return not self.modifiers_held

    def foreground(self):
        return self.fg

    def root_window(self, hwnd):
        return hwnd

    def activate(self, hwnd):
        self.activations += 1
        if not self.refuse_activation:
            self.fg = hwnd
        return not self.refuse_activation

    def window_pid(self, hwnd):
        return 4242

    def process_name(self, pid):
        return self.app

    def window_title(self, hwnd):
        return "Report.docx - Word"

    def is_elevated(self, pid):
        return self.elevated_target

    def send_copy(self, ctrl_insert=False):
        self.copies += 1
        self.copy_keys.append("ctrl+insert" if ctrl_insert else "ctrl+c")
        if self.on_copy:
            self.on_copy(self)
        if self.fg == self.target and self.selected:
            self.board = {"text": self.selected, "html": self.html, "formats": set(), "custom": self.custom}
            self.seq += 1
        if self.after_copy:
            self.after_copy(self)
        return True

    def send_paste(self, shift_insert=False):
        if self.fg == self.target and self.selected:
            new = self.board["text"]
            self.document = self.document.replace(self.selected, new, 1)
            self.pastes.append(new)
            self.selected = ""   # a paste leaves the caret after the new text
        return True

    def sequence(self):
        return self.seq

    def clipboard_busy(self):
        return False

    def select(self, text: str) -> None:
        self.selected = text


class FakeClip:
    def __init__(self, win: FakeWin, snapshot_ok: bool = True) -> None:
        self.win, self.snapshot_ok = win, snapshot_ok
        self.restores = 0

    def snapshot(self):
        return [("text", self.win.board.get("text", ""))] if self.snapshot_ok else None

    def restore(self, items):
        self.win.board = {"text": dict(items).get("text", "")}
        self.win.seq += 1
        self.restores += 1

    def set_text(self, text, hide=True):
        self.win.board = {"text": text, "hidden": hide}
        self.win.seq += 1
        return self.win.seq

    def read(self):
        return {"text": "", "html": "", "formats": set(), "custom": "", **self.win.board}


def grab(win: FakeWin, clip: FakeClip | None = None, elevated: bool = False):
    return selection.capture(win, clip or FakeClip(win), 100, elevated=elevated, copy_wait=0.05)


class Capture(unittest.TestCase):
    def test_reads_the_selection_and_puts_your_clipboard_back(self):
        win = FakeWin()
        clip = FakeClip(win)
        sel = grab(win, clip)
        self.assertEqual((sel.text, sel.app, sel.window, sel.target), (TEXT, "winword.exe", "Report.docx - Word", 100))
        self.assertEqual(win.board["text"], "what you copied earlier")
        self.assertEqual((win.copies, clip.restores), (1, 1))

    def test_refusals(self):
        cases = [
            (dict(selected=""), "Nothing selected"),
            (dict(app="windowsterminal.exe"), "terminal"),
            (dict(html="<html><body><img src='x.png'> text</body></html>"), "picture or a table"),
            (dict(html="<TABLE><tr><td>a</td></tr></TABLE>"), "picture or a table"),
            (dict(custom='{"vscode-editor-data":{"isFromEmptySelection": true}}'), "Nothing selected"),
            (dict(selected=" \r\n"), "no text"),
        ]
        for kwargs, words in cases:
            win = FakeWin(**kwargs)
            with self.assertRaises(selection.SelectionError, msg=kwargs) as cm:
                grab(win)
            self.assertIn(words, cm.exception.title, kwargs)
            self.assertEqual(win.board["text"], "what you copied earlier", kwargs)   # clipboard as it was

    def test_elevated_or_unknown_target(self):
        for value in (True, None):
            win = FakeWin()
            win.elevated_target = value
            with self.assertRaises(selection.SelectionError):
                grab(win)
            self.assertEqual(win.copies, 0)
        win = FakeWin()
        win.elevated_target = True
        self.assertEqual(grab(win, elevated=True).text, TEXT)   # we run elevated too: allowed

    def test_keys_held_and_no_window(self):
        win = FakeWin()
        win.modifiers_held = True
        with self.assertRaises(selection.SelectionError):
            grab(win)
        with self.assertRaises(selection.SelectionError):
            selection.capture(FakeWin(), FakeClip(FakeWin()), 0, elevated=False)

    def test_hands_the_focus_back_first(self):
        win = FakeWin()
        win.fg = 555   # our menu
        self.assertEqual(grab(win).text, TEXT)
        self.assertEqual(win.fg, 100)
        win = FakeWin()
        win.fg, win.refuse_activation = 555, True
        with self.assertRaises(selection.SelectionError):
            grab(win)

    def test_editors_with_a_terminal_panel_copy_with_ctrl_insert(self):
        win = FakeWin(app="code.exe")
        grab(win)
        self.assertEqual(win.copy_keys, ["ctrl+insert"])
        win = FakeWin()
        grab(win)
        self.assertEqual(win.copy_keys, ["ctrl+c"])

    def test_text_inside_a_table_cell_is_not_a_table(self):
        cell = ("Version:0.9\r\n<html><body><table><tr><td><!--StartFragment-->just some text<!--EndFragment-->"
                "</td></tr></table></body></html>")
        self.assertEqual(grab(FakeWin(html=cell)).text, TEXT)
        whole = "<html><body><!--StartFragment--><table><tr><td>a</td></tr></table><!--EndFragment--></body></html>"
        with self.assertRaises(selection.SelectionError):
            grab(FakeWin(html=whole))

    def test_full_clipboard_is_never_lost(self):
        win = FakeWin()
        with self.assertRaises(selection.SelectionError) as cm:
            grab(win, FakeClip(win, snapshot_ok=False))
        self.assertIn("64 MB", cm.exception.title)
        self.assertEqual(win.copies, 0)


class Replace(unittest.TestCase):
    def put(self, win: FakeWin, sel, text: str, clip: FakeClip | None = None):
        return selection.replace(win, clip or FakeClip(win), sel, text, copy_wait=0.05, settle=0)

    def test_pastes_over_the_same_selection(self):
        win = FakeWin()
        sel = grab(win)
        outcome, detail = self.put(win, sel, FIXED)
        self.assertEqual(outcome, "replaced", detail)
        self.assertEqual((win.document, win.pastes), (FIXED, [FIXED]))
        self.assertEqual(win.board["text"], "what you copied earlier")

    def test_selection_changed_meanwhile(self):
        win = FakeWin()
        sel = grab(win)
        win.select("another sentence")
        outcome, detail = self.put(win, sel, FIXED)
        self.assertEqual(outcome, "copied")
        self.assertIn("selection changed", detail)
        self.assertEqual((win.pastes, win.board["text"], win.board["hidden"]), ([], FIXED, False))

    def test_selection_gone_or_window_switched(self):
        win = FakeWin()
        sel = grab(win)
        win.select("")
        self.assertEqual(self.put(win, sel, FIXED)[0], "copied")
        win = FakeWin()
        sel = grab(win)
        win.fg, win.refuse_activation = 777, True
        outcome, detail = self.put(win, sel, FIXED)
        self.assertEqual(outcome, "copied")
        self.assertIn("another window", detail)
        self.assertEqual(win.pastes, [])

    def test_never_pulls_the_focus_back_from_another_app(self):
        win = FakeWin()
        sel = grab(win)
        win.fg = 777                                 # you moved on to another app while the model worked
        outcome, _detail = self.put(win, sel, FIXED)
        self.assertEqual((outcome, win.fg, win.activations, win.pastes), ("copied", 777, 0, []))
        win = FakeWin()
        sel = grab(win)
        win.fg = 555                                 # one of our windows (a menu): hand the focus back
        outcome, _ = selection.replace(win, FakeClip(win), sel, FIXED, ours=lambda h: h == 555, copy_wait=0.05,
                                       settle=0)
        self.assertEqual((outcome, win.fg, win.pastes), ("replaced", 100, [FIXED]))

    def test_window_switch_between_check_and_paste(self):
        win = FakeWin()
        sel = grab(win)
        win.after_copy = lambda w: setattr(w, "fg", 777)
        outcome, detail = self.put(win, sel, FIXED)
        self.assertEqual((outcome, win.pastes), ("copied", []))
        self.assertIn("another window", detail)

    def test_whole_line_copy_at_the_check(self):
        win = FakeWin()
        sel = grab(win)
        win.custom = '{"isFromEmptySelection":true}'   # the selection is gone; VS Code copied the caret's line
        outcome, detail = self.put(win, sel, FIXED)
        self.assertEqual((outcome, win.pastes), ("copied", []))
        self.assertIn("no longer selected", detail)

    def test_unsaveable_clipboard_leaves_everything_alone(self):
        win = FakeWin()
        sel = grab(win)
        outcome, _ = self.put(win, sel, FIXED, FakeClip(win, snapshot_ok=False))
        self.assertEqual(outcome, "skipped")
        self.assertEqual((win.pastes, win.copies, win.board["text"]), ([], 1, "what you copied earlier"))

    def test_shift_insert_for_mintty(self):
        win = FakeWin(app="mintty.exe")
        win.send_paste = mock.Mock(return_value=True)
        sel = selection.Selection(TEXT, 100, "mintty.exe", "")
        self.put(win, sel, FIXED)
        win.send_paste.assert_called_once_with(shift_insert=True)


# ---------------------------------------------------------------- the whole flow, with fakes

class RecordingUI:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __getattr__(self, kind):
        if kind in ("working", "done", "error", "cancelled", "note"):
            return lambda title, body="", hint="": self.calls.append((kind, title, hint))
        raise AttributeError(kind)

    def last(self, kind: str) -> str:
        return next((t for k, t, _h in reversed(self.calls) if k == kind), "")

    def hint(self, kind: str) -> str:
        return next((h for k, _t, h in reversed(self.calls) if k == kind), "")


class Flow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = RefineLog(Path(self.tmp.name) / "refine-log.jsonl")
        self.win = FakeWin()
        self.clip = FakeClip(self.win)
        self.ui = RecordingUI()
        self.esc: list[bool] = []
        self.reply = refine.Result(FIXED, True, "", 0.5, suggestion=FIXED, served="qwen3.5:9b")
        self.gate: threading.Event | None = None
        self.busy_reason = ""
        self.cfg = refine.Config()
        self.refiner = Refiner(call=lambda fn: fn(self.win, self.clip), target=lambda: 100, ui=self.ui,
                               cfg=lambda: self.cfg, refine_fn=self.fake_model, log=self.log, esc=self.esc.append,
                               elevated=False, busy_elsewhere=lambda: self.busy_reason)
        self.sent: list[tuple[str, str]] = []
        # The real capture and replace, without their waits.
        for name, fast in (("capture", lambda ws, clip, target, elevated: selection.capture(
                ws, clip, target, elevated=elevated, copy_wait=0.05)),
                           ("replace", lambda ws, clip, sel, text, **kw: selection.replace(
                ws, clip, sel, text, copy_wait=0.05, settle=0, **kw))):
            patcher = mock.patch(f"stacklib.dictation.refiner.{name}", side_effect=fast)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def fake_model(self, text, style, *, model, timeout):
        self.sent.append((text, style.id))
        if self.gate is not None:
            self.gate.wait(5)
        return self.reply

    def wait(self):
        """Until no job runs, a cancelled one still waiting for the model included."""
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and (self.refiner.busy or any(
                t.name in ("dictation-refine", "dictation-revert") for t in threading.enumerate())):
            time.sleep(0.01)
        self.assertFalse(self.refiner.busy)

    def test_refine_replaces_and_logs_before_and_after(self):
        self.assertTrue(self.refiner.start("", "test"))
        self.wait()
        self.assertEqual(self.win.document, FIXED)
        [entry] = self.log.entries()
        self.assertEqual((entry["kind"], entry["status"], entry["style"]), ("refine", "replaced", "polish"))
        self.assertEqual((entry["before"], entry["after"]), (TEXT, FIXED))
        self.assertEqual((entry["app"], entry["window"], entry["served"]), ("winword.exe", "Report.docx - Word", "qwen3.5:9b"))
        self.assertEqual(self.ui.last("done"), "Replaced with Polish")
        self.assertEqual(self.esc, [True, False])
        self.assertEqual(self.sent, [(TEXT, "polish")])
        self.assertEqual(self.refiner.last_id, entry["id"])
        self.assertIn("keeps the original for 30 minutes", self.ui.hint("done"))

    def test_style_menu_refines_in_the_window_it_was_opened_from(self):
        """The style menu's invisible anchor window is in front when you pick a style: the job must use the window
        the hotkey was pressed in, not whatever target() finds then."""
        self.refiner.target = lambda: 999   # our anchor window, say
        self.assertTrue(self.refiner.start("grammar", "style-menu", target=100))
        self.wait()
        self.assertEqual(self.win.document, FIXED)
        self.assertEqual(self.sent, [(TEXT, "grammar")])

    def test_without_a_target_the_window_in_front_is_used(self):
        self.refiner.target = lambda: 999
        self.refiner.start("grammar", "menu")
        self.wait()
        self.assertEqual(self.win.document, TEXT)   # window 999 has no selection here

    def test_revert_takes_a_target_too(self):
        self.refiner.start("", "test")
        self.wait()
        self.win.select(FIXED)
        self.refiner.target = lambda: 999
        self.assertTrue(self.refiner.revert("", "style-menu", target=100))
        self.wait()
        self.assertEqual(self.win.document, TEXT)

    def test_other_style_from_the_menu(self):
        self.refiner.start("bullets", "menu")
        self.wait()
        self.assertEqual(self.sent[0][1], "bullets")
        self.assertEqual(self.log.entries()[0]["style_name"], "Bullet points")

    def test_rejected_reply_keeps_your_text_and_the_suggestion(self):
        self.reply = refine.Result(TEXT, False, "the model answered instead of rewriting", 0.4, suggestion="Sure!")
        self.refiner.start()
        self.wait()
        self.assertEqual((self.win.document, self.win.pastes), (TEXT, []))
        entry = self.log.entries()[0]
        self.assertEqual((entry["status"], entry["after"], entry["note"]),
                         ("rejected", "Sure!", "the model answered instead of rewriting"))
        self.assertEqual(self.ui.last("error"), "Kept your text")

    def test_gateway_down_and_unchanged(self):
        self.reply = refine.Result(TEXT, False, "the gateway is not reachable (refused)", 2.0)
        self.refiner.start()
        self.wait()
        self.assertEqual(self.log.entries()[0]["status"], "failed")
        self.win.select(TEXT)
        self.reply = refine.Result(TEXT, True, "no changes needed", 0.3, suggestion=TEXT, unchanged=True)
        self.refiner.start()
        self.wait()
        self.assertEqual(self.log.entries()[0]["status"], "unchanged")
        self.assertEqual(self.win.pastes, [])

    def test_cancel_while_the_model_works(self):
        self.gate = threading.Event()
        self.refiner.start()
        deadline = time.monotonic() + 5
        while not self.sent and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(self.refiner.cancel())
        self.assertFalse(self.refiner.cancel())   # once
        self.gate.set()
        self.wait()
        self.assertEqual((self.win.document, self.win.pastes), (TEXT, []))
        self.assertEqual(self.log.entries()[0]["status"], "cancelled")
        self.assertEqual(self.ui.last("cancelled"), "Cancelled")

    def test_cancel_frees_the_button_and_esc_stays_with_the_next_job(self):
        self.gate = threading.Event()
        self.refiner.start()
        deadline = time.monotonic() + 5
        while not self.sent and time.monotonic() < deadline:
            time.sleep(0.01)
        first = self.refiner.job
        self.assertTrue(self.refiner.cancel())
        self.assertFalse(self.refiner.busy)              # free at once, while the first still waits for the model
        second_gate = threading.Event()

        def slow_again(text, style, *, model, timeout):
            self.sent.append((text, style.id))
            second_gate.wait(5)
            return self.reply

        self.refiner.refine_fn = slow_again
        self.assertTrue(self.refiner.start())
        while len(self.sent) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.05)
        self.assertEqual(self.esc, [True, False, True])  # the second job holds Esc
        self.gate.set()                                  # the first finishes: it must not release the second's Esc
        time.sleep(0.3)
        self.assertEqual(self.esc, [True, False, True])
        self.assertIsNot(self.refiner.job, first)
        second_gate.set()
        self.wait()
        self.assertEqual(self.esc, [True, False, True, False])
        self.assertEqual(sorted(e["status"] for e in self.log.entries()), ["cancelled", "replaced"])

    def test_one_at_a_time_and_not_while_dictating(self):
        self.gate = threading.Event()
        self.assertTrue(self.refiner.start())
        self.assertFalse(self.refiner.start())
        self.assertEqual(self.ui.last("note"), "Still working on the last selection")
        self.gate.set()
        self.wait()
        self.busy_reason = "Finish dictating first"
        self.assertFalse(self.refiner.start())
        self.assertEqual(self.ui.last("note"), "Finish dictating first")

    def test_too_long(self):
        self.cfg = refine.Config(max_chars=200)
        self.win = FakeWin(selected="word " * 100)
        self.clip = FakeClip(self.win)
        self.refiner.start()
        self.wait()
        self.assertEqual((self.sent, self.log.entries()), ([], []))
        self.assertEqual(self.ui.last("error"), "The selection is too long")

    def test_nothing_selected(self):
        self.win.select("")
        self.refiner.start()
        self.wait()
        self.assertEqual(self.ui.last("error"), "Nothing selected")
        self.assertEqual(self.sent, [])

    def test_revert_puts_the_original_back(self):
        self.refiner.start()
        self.wait()
        refined = self.log.entries()[0]
        self.win.select(FIXED + "\r\n")              # you select the refined text, paragraph mark included
        self.win.document = FIXED + "\r\n"
        self.assertTrue(self.refiner.revert("", "menu"))
        self.wait()
        self.assertEqual(self.win.document, TEXT + "\r\n")
        entry = self.log.entries()[0]
        self.assertEqual((entry["kind"], entry["of"], entry["status"]), ("revert", refined["id"], "replaced"))
        self.assertEqual((entry["before"], entry["after"]), (FIXED + "\r\n", TEXT + "\r\n"))
        self.assertEqual(self.ui.last("done"), "Original put back")
        self.assertEqual(self.log.reverted_ids(), {refined["id"]})

    def test_revert_needs_a_matching_selection(self):
        self.refiner.start()
        self.wait()
        refined = self.log.entries()[0]
        self.win.select("Some text that was never refined.")
        self.refiner.revert()
        self.wait()
        self.assertEqual(self.ui.last("error"), "Not in the refine history")
        self.refiner.revert(refined["id"])
        self.wait()
        self.assertEqual(self.ui.last("error"), "The selected text is not that suggestion")
        self.win.select(FIXED.replace("Thursday", "Friday"))   # edited a little after the refine: still that entry
        self.win.document = self.win.selected
        self.refiner.revert(refined["id"])
        self.wait()
        self.assertEqual(self.win.document, TEXT)
        self.assertIn("Edits you made after it were undone too", self.ui.hint("done"))


class Wiring(unittest.TestCase):
    def test_control_actions(self):
        ok = {"Host": "127.0.0.1:8790"}
        for name in ("refine", "revert", "show_refine", "hide_refine"):
            self.assertIsNone(control.check_request("POST", f"/{name}", ok, 8790), name)
            self.assertEqual(control.check_request("GET", f"/{name}", ok, 8790)[0], 405, name)

    def test_hotkey_choices(self):
        for choice in hotkey.REFINE_CHOICES:
            hotkey.parse(choice)
        self.assertEqual(hotkey.REFINE_CHOICES[0], refine.Config().hotkey)
        self.assertNotIn(prof.load_defaults()["dictation"]["hotkey"], hotkey.REFINE_CHOICES)

    def test_menu_hotkey_choices(self):
        for choice in hotkey.MENU_CHOICES:
            hotkey.parse(choice)
        self.assertEqual(hotkey.MENU_CHOICES[0], refine.Config().menu_hotkey)
        self.assertEqual(prof.load_defaults()["refine"]["menu_hotkey"], refine.Config().menu_hotkey)
        taken = {hotkey.parse(prof.load_defaults()["dictation"]["hotkey"]), hotkey.parse(refine.Config().hotkey)}
        self.assertEqual([c for c in hotkey.MENU_CHOICES if hotkey.parse(c) in taken], [])
        self.assertTrue(all(hotkey.is_off(v) for v in ("", " off ", "None")))
        self.assertFalse(hotkey.is_off("ctrl+alt+r"))
        menu = next(s for s in settings.SETTINGS if settings.setting_id(s) == "refine.menu_hotkey")
        self.assertEqual(menu.effect, "dictation")   # hotkeys are registered when voice typing starts

    def test_style_menu_rows(self):
        from stacklib.dictation.overlay import style_menu_items

        many = list(refine.BUILTIN) + [refine.Style(f"mine{i}", f"Mine {i}", "x") for i in range(4)]
        rows = style_menu_items(many, "concise", "Ctrl+Alt+R")
        picks = [r for r in rows if r[1] not in (None, "revert")]
        self.assertEqual([r[1] for r in picks], [s.id for s in many])
        self.assertEqual([r[0][0] for r in picks[:9]], [str(i) for i in range(1, 10)])   # 1-9 pick from the keys
        self.assertTrue(all(r[2] == 0 for r in picks[:9]) and all(r[2] == -1 for r in picks[9:]))
        self.assertEqual([r[1] for r in picks if r[3]], ["concise"])
        self.assertEqual(rows[-1][1], "revert")
        self.assertIsNone(rows[0][1])   # the heading

    def test_tray_settings(self):
        ids = {settings.setting_id(s) for s in settings.SETTINGS}
        self.assertTrue({"refine.hotkey", "refine.default", "refine.model", "refine.button"} <= ids)
        p = {"models": {}, "observability": {}, "services": {}, "ollama_env": {}, "dictation": {},
             "refine": {"default": "concise", "button": False}}
        values = settings.current_values(p)
        self.assertEqual((values["refine.default"], values["refine.button"]), ("concise", False))

    def test_refine_button_toggles_without_a_restart(self):
        button = next(s for s in settings.SETTINGS if settings.setting_id(s) == "refine.button")
        new = {"name": "T", "services": {"dictation": "native"}, "ports": {"dictation": 8790},
               "dictation": {}, "refine": {"button": False}}
        with mock.patch.object(settings, "save", return_value=[button]), \
                mock.patch.object(settings.prof, "resolve_profile", return_value=new), \
                mock.patch.object(settings.services, "_task_managed", return_value=set()), \
                mock.patch.object(settings.services, "stop") as stop, \
                mock.patch.object(control, "call", return_value={"ok": True}) as call:
            settings.apply({"name": "T"}, {"refine.button": False}, log=lambda m: None)
        call.assert_called_once_with(8790, "hide_refine")
        stop.assert_not_called()

    def test_keep_minutes_setting(self):
        keep = next(s for s in settings.SETTINGS if settings.setting_id(s) == "refine.keep_minutes")
        self.assertEqual((keep.effect, settings._to_file_value(keep, "60")), ("refine", 60))
        self.assertIn(str(int(refine.Config().keep_minutes)), keep.choices)
        values = settings.current_values({"models": {}, "observability": {}, "services": {}, "ollama_env": {},
                                          "dictation": {}, "refine": {"keep_minutes": 30}})
        self.assertEqual(values["refine.keep_minutes"], "30")

    def test_style_and_model_need_no_restart(self):
        for sid in ("refine.default", "refine.model", "refine.keep_minutes"):
            setting = next(s for s in settings.SETTINGS if settings.setting_id(s) == sid)
            new = {"name": "T", "services": {"dictation": "native"}, "ports": {"dictation": 8790}, "dictation": {},
                   "refine": {}}
            with mock.patch.object(settings, "save", return_value=[setting]), \
                    mock.patch.object(settings.prof, "resolve_profile", return_value=new), \
                    mock.patch.object(settings.services, "_task_managed", return_value=set()), \
                    mock.patch.object(settings.services, "stop") as stop, \
                    mock.patch.object(settings.services, "start") as start, \
                    mock.patch.object(control, "call") as call:
                settings.apply({"name": "T"}, {sid: "x"}, log=lambda m: None)
            stop.assert_not_called()
            start.assert_not_called()
            call.assert_not_called()

    def test_machine_file_template(self):
        from stacklib import dictation
        import yaml

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "T.yaml"
            path.write_text("name: T\n# notes\ndictation:\n  language: en\n", encoding="utf-8")
            self.assertTrue(dictation.ensure_refine_section(path))
            self.assertFalse(dictation.ensure_refine_section(path))
            text = path.read_text(encoding="utf-8")
            self.assertIn("# notes", text)
            self.assertEqual(text.count("refine:"), 1)
            parsed = yaml.safe_load(text)
            self.assertEqual(parsed["dictation"], {"language": "en"})
            self.assertEqual(prof.resolve_refine({"prompts": {}}, parsed["refine"] or {})["prompts"], {})
            with mock.patch("stacklib.profile.machine_file", return_value=path):
                dictation.save_setting({"name": "T"}, "default", "concise", section="refine")
            self.assertEqual(yaml.safe_load(path.read_text(encoding="utf-8"))["refine"]["default"], "concise")


if __name__ == "__main__":
    unittest.main()


class Consistency(unittest.TestCase):
    """The buttons, menus and history window call the app by name, and a name the App class lacks fails only when you
    click. Review found two (the refine menu asked for refine_styles(); RefineUI swallowed paste_last()). App imports
    numpy, which the project environment lacks, so this reads the source."""

    BASE = Path(__file__).resolve().parents[1] / "scripts" / "stacklib" / "dictation"

    def _app_class(self):
        import ast

        tree = ast.parse((self.BASE / "app.py").read_text(encoding="utf-8"))
        return tree, next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App")

    def test_every_app_call_exists(self):
        import ast

        _tree, cls = self._app_class()
        have = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        have |= {n.attr for n in ast.walk(cls) if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
                 and isinstance(n.value, ast.Name) and n.value.id == "self"}
        for name in ("overlay.py", "history.py"):
            used = set()
            for n in ast.walk(ast.parse((self.BASE / name).read_text(encoding="utf-8"))):
                if not isinstance(n, ast.Attribute):
                    continue
                v = n.value
                if (isinstance(v, ast.Name) and v.id == "app") or (
                        isinstance(v, ast.Attribute) and v.attr == "app" and isinstance(v.value, ast.Name)
                        and v.value.id == "self"):
                    used.add(n.attr)
            self.assertEqual(sorted(used - have), [], f"{name} uses names the App class does not have")
        for kept in ("paste_last", "copy_last", "refine_choices", "remember_position", "set_refine_option"):
            self.assertIn(kept, have)

    def test_app_calls_into_the_overlay_exist(self):
        import ast

        tree = ast.parse((self.BASE / "overlay.py").read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Overlay")
        have = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        _tree, app = self._app_class()
        used = {n.attr for n in ast.walk(app) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Attribute)
                and n.value.attr == "overlay"}
        self.assertIn("style_menu_at", used)
        self.assertEqual(sorted(used - have - {"root", "visible"}), [], "app.py calls names Overlay lacks")

    def test_refiner_is_built_with_its_own_arguments(self):
        import ast
        import inspect

        tree, _cls = self._app_class()
        call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Refiner")
        accepted = set(inspect.signature(Refiner.__init__).parameters) - {"self"}
        self.assertEqual({k.arg for k in call.keywords} - accepted, set())
