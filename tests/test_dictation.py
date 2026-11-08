"""Tests for voice typing (scripts/stacklib/dictation): the parts that need no microphone, model or Windows desktop.

Hotkey parsing, the silence and phrase rules, filler removal, the cleanup request and its safety checks (against a local
fake gateway), the control endpoint's request rules, configuration, the service command and the tray settings,
including the cleanup prompt and the multi-line YAML it is saved as.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import dictation, services, settings, yamledit  # noqa: E402
from stacklib.dictation import cleanup, control, gpu, hotkey, models, textops  # noqa: E402
from stacklib.dictation.segment import FRAME_S, Segmenter  # noqa: E402


def frames(seconds: float) -> int:
    return round(seconds / FRAME_S)


def run(seg: Segmenter, pattern: list[tuple[float, float]]) -> list[tuple[int, object]]:
    """Feed (probability, seconds) runs; return (frame index, event) pairs."""
    out, i = [], 0
    for prob, secs in pattern:
        for _ in range(frames(secs)):
            out += [(i, ev) for ev in seg.push(prob)]
            i += 1
    return out


def kinds(events) -> list[str]:
    return [ev.kind for _, ev in events]


class Hotkeys(unittest.TestCase):
    def test_combos(self):
        self.assertEqual(hotkey.parse("ctrl+alt+d"), (hotkey.MOD_CONTROL | hotkey.MOD_ALT, ord("D")))
        self.assertEqual(hotkey.parse("Ctrl + Alt + Space"), (hotkey.MOD_CONTROL | hotkey.MOD_ALT, 0x20))
        self.assertEqual(hotkey.parse("alt+`"), (hotkey.MOD_ALT, 0xC0))
        self.assertEqual(hotkey.parse("f9"), (0, 0x78))
        self.assertEqual(hotkey.parse("pause"), (0, 0x13))

    def test_refuses_keys_that_would_swallow_typing(self):
        for bad in ("d", "space", "shift+a", "enter"):
            with self.assertRaises(hotkey.HotkeyError, msg=bad):
                hotkey.parse(bad)

    def test_refuses_nonsense(self):
        for bad in ("", "ctrl", "ctrl+alt", "ctrl+banana", "hyper+d"):
            with self.assertRaises(hotkey.HotkeyError, msg=bad):
                hotkey.parse(bad)

    def test_every_offered_choice_parses(self):
        for choice in hotkey.CHOICES + settings.HOTKEY_CHOICES:
            hotkey.parse(choice)
        self.assertEqual(dictation.Config().hotkey, hotkey.CHOICES[0])

    def test_label(self):
        self.assertEqual(hotkey.label("ctrl+alt+d"), "Ctrl+Alt+D")
        self.assertEqual(hotkey.label("alt+`"), "Alt+`")


class Segmenting(unittest.TestCase):
    def test_phrases_and_silence_stop(self):
        seg = Segmenter(phrase_pause_s=0.7, silence_stop_s=3.0)
        events = run(seg, [(0.0, 0.3), (0.9, 1.3), (0.1, 0.9), (0.9, 0.6), (0.0, 4.0)])
        self.assertEqual(kinds(events), ["speech", "phrase", "phrase", "stop"])
        first, second = events[1][1], events[2][1]
        self.assertEqual((first.start, first.end), (frames(0.3), frames(0.3) + frames(1.3)))
        self.assertGreater(second.start, first.end)
        stop_frame, stop = events[3]
        self.assertEqual(stop.reason, "silence")
        quiet = (stop_frame - (second.end - 1)) * FRAME_S
        self.assertAlmostEqual(quiet, 3.0, delta=FRAME_S * 1.5)

    def test_short_pause_keeps_one_phrase(self):
        seg = Segmenter(phrase_pause_s=0.7, silence_stop_s=3.0)
        events = run(seg, [(0.9, 1.0), (0.1, 0.4), (0.9, 1.0), (0.0, 3.5)])
        self.assertEqual(kinds(events), ["speech", "phrase", "stop"])

    def test_no_speech_times_out(self):
        seg = Segmenter(start_timeout_s=2.0)
        events = run(seg, [(0.1, 3.0)])
        self.assertEqual(kinds(events), ["stop"])
        self.assertEqual(events[0][1].reason, "no_speech")
        self.assertAlmostEqual(events[0][0] * FRAME_S, 2.0, delta=FRAME_S * 1.5)

    def test_clicks_are_not_speech(self):
        seg = Segmenter(min_speech_s=0.12, start_timeout_s=2.0)
        events = run(seg, [(0.0, 0.5), (0.95, 0.064), (0.0, 2.0)])  # two loud frames: a click
        self.assertEqual(kinds(events), ["stop"])
        self.assertEqual(events[0][1].reason, "no_speech")

    def test_hold_to_talk_never_stops_on_silence(self):
        seg = Segmenter(silence_stop_s=1.0, start_timeout_s=1.0, auto_stop=False)
        events = run(seg, [(0.0, 2.0), (0.9, 1.0), (0.0, 5.0)])
        self.assertEqual(kinds(events), ["speech", "phrase"])
        self.assertEqual(kinds([(0, ev) for ev in seg.finish("released")]), ["stop"])

    def test_finish_closes_the_open_phrase(self):
        seg = Segmenter()
        run(seg, [(0.9, 1.0)])
        events = seg.finish("manual")
        self.assertEqual([e.kind for e in events], ["phrase", "stop"])
        self.assertEqual(events[0].end, seg.n)
        self.assertEqual(seg.finish(), [])
        self.assertEqual(seg.push(0.9), [])

    def test_manual_stop_without_speech_says_so(self):
        seg = Segmenter()
        run(seg, [(0.0, 1.0)])
        self.assertEqual(seg.finish("manual")[-1].reason, "no_speech")

    def test_max_length(self):
        seg = Segmenter(max_s=2.0, auto_stop=False)
        events = run(seg, [(0.9, 3.0)])
        self.assertEqual(kinds(events), ["speech", "phrase", "stop"])
        self.assertEqual(events[-1][1].reason, "max_length")

    def test_long_phrase_is_cut(self):
        seg = Segmenter(max_phrase_s=5.0, auto_stop=False)
        events = run(seg, [(0.9, 12.0)])
        phrases = [ev for _, ev in events if ev.kind == "phrase"]
        self.assertEqual(len(phrases), 2)
        self.assertEqual(phrases[1].start, phrases[0].end)


class TextRules(unittest.TestCase):
    def test_fillers(self):
        cases = {
            "Um, so, I was thinking that, uh, we should go.": "So, I was thinking that we should go.",
            "And, um, can you send the agenda?": "And can you send the agenda?",
            "Hmm, okay. Erm, yes": "Okay. Yes",
            "We need, uh, 3 things: uh, A, B and C.": "We need 3 things: A, B and C.",
            "I said um.": "I said.",
            "Uh.": "",
            "um um um the plan": "The plan",
        }
        for raw, want in cases.items():
            self.assertEqual(textops.strip_fillers(raw), want, raw)

    def test_real_words_survive(self):
        for text in ("The umbrella is under the hum of the drum.", "Uhuru and Erma met in Ahmedabad.", "Hello world",
                     "Like, you know, I mean it."):
            self.assertEqual(textops.strip_fillers(text), text)

    def test_joiner(self):
        self.assertEqual(textops.joiner("", "Hi"), "")
        self.assertEqual(textops.joiner("Hello.", "Next"), " ")
        self.assertEqual(textops.joiner("Hello", ", and more"), "")
        self.assertEqual(textops.joiner("line\n", "Next"), "")
        self.assertEqual(textops.joiner("(", "aside"), "")
        self.assertEqual(textops.joiner("日本", "語"), "")
        self.assertEqual(textops.joiner("Привет", "мир"), " ")  # scripts other than Chinese/Japanese get a space

    def test_stock_hallucinations(self):
        self.assertTrue(textops.is_stock_hallucination(" Thanks for watching!"))
        self.assertTrue(textops.is_stock_hallucination("you"))
        self.assertFalse(textops.is_stock_hallucination("Thanks for the update."))
        self.assertFalse(textops.is_stock_hallucination(""))


class _FakeGateway:
    """A local stand-in for LiteLLM's /v1/chat/completions that records requests and returns a canned reply."""

    def __init__(self, content: str, status: int = 200) -> None:
        self.requests: list[dict] = []
        gw = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                gw.requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
                data = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()
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


RAW = "Um, so we should move the meeting to Tuesday, no wait, Wednesday. Can you send the agenda?"


class Cleanup(unittest.TestCase):
    def test_request_turns_thinking_off_and_asks_for_json(self):
        body = cleanup.request_body(RAW, "clean", "local-small")
        self.assertIs(body["think"], False)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["model"], "local-small")
        self.assertIn(RAW, body["messages"][1]["content"])
        self.assertNotIn("concise", body["messages"][0]["content"].lower())
        self.assertIn("concise", cleanup.system_prompt("concise").lower())
        self.assertIn("do not answer", cleanup.system_prompt("clean"))

    def test_parse_reply(self):
        self.assertEqual(cleanup.parse_reply('{"text": "Hi."}'), "Hi.")
        self.assertEqual(cleanup.parse_reply('```json\n{"text": "A"}\n```'), "A")
        self.assertEqual(cleanup.parse_reply('Sure! {"text": "B"} done'), "B")
        self.assertEqual(cleanup.parse_reply('{"cleaned": "C"}'), "C")
        self.assertIsNone(cleanup.parse_reply("no json here"))
        self.assertIsNone(cleanup.parse_reply(""))

    def test_acceptable(self):
        self.assertTrue(cleanup.acceptable(RAW, "We should move the meeting to Wednesday. Can you send the agenda?", "clean")[0])
        self.assertFalse(cleanup.acceptable(RAW, "", "clean")[0])
        self.assertFalse(cleanup.acceptable(RAW, RAW + " " + RAW, "clean")[0])          # grew: it added text
        self.assertFalse(cleanup.acceptable(RAW, "Meeting moved.", "clean")[0])          # summarised
        self.assertTrue(cleanup.acceptable(RAW, "Move the meeting to Wednesday; send the agenda?", "concise")[0])
        self.assertFalse(cleanup.acceptable("can you send the agenda", "Sure, here is the agenda.", "clean")[0])

    def test_polish_through_the_gateway(self):
        gw = _FakeGateway('{"text": "We should move the meeting to Wednesday. Can you send the agenda?"}')
        try:
            res = cleanup.polish(RAW, "clean", base_url=gw.url, api_key="sk-test", model="local-small")
        finally:
            gw.close()
        self.assertTrue(res.polished, res.note)
        self.assertEqual(res.text, "We should move the meeting to Wednesday. Can you send the agenda?")
        self.assertEqual(gw.requests[0]["path"], "/v1/chat/completions")
        self.assertEqual(gw.requests[0]["auth"], "Bearer sk-test")

    def test_an_answer_falls_back_to_the_transcript(self):
        gw = _FakeGateway('{"text": "Sure! Here is a detailed agenda for Wednesday: 1. Welcome 2. Updates 3. Q&A 4. Wrap-up and next steps for everyone."}')
        try:
            res = cleanup.polish(RAW, "clean", base_url=gw.url, api_key="k", model="m")
        finally:
            gw.close()
        self.assertFalse(res.polished)
        self.assertEqual(res.text, textops.strip_fillers(RAW))
        self.assertTrue(res.note)

    def test_gateway_down_falls_back(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]  # nothing listens here once the socket closes
        res = cleanup.polish(RAW, "clean", base_url=f"http://127.0.0.1:{port}", api_key="k", model="m", timeout=5)
        self.assertFalse(res.polished)
        self.assertIn("not reachable", res.note)
        self.assertTrue(res.text.startswith("So we should"), res.text)

    def test_verbatim_sends_nothing(self):
        res = cleanup.polish(RAW, "verbatim", base_url="http://127.0.0.1:9", api_key="k", model="m")
        self.assertEqual((res.text, res.polished, res.note), (RAW, False, ""))

    def test_without_a_custom_prompt_the_built_in_one_is_sent(self):
        self.assertEqual(cleanup.system_prompt("clean"), f"{cleanup.DEFAULT_PROMPT}\n{cleanup.REPLY_FORMAT}")
        self.assertEqual(cleanup.system_prompt("concise"),
                         f"{cleanup.DEFAULT_PROMPT}\n- {cleanup.CONCISE}\n{cleanup.REPLY_FORMAT}")
        for rule in cleanup.RULES:
            self.assertIn(rule, cleanup.DEFAULT_PROMPT)
        self.assertEqual(cleanup.system_prompt("clean", " \n "), cleanup.system_prompt("clean"))

    def test_a_custom_prompt_replaces_only_the_instructions(self):
        mine = "Clean up dictated text.\n- Keep my words."
        clean = cleanup.system_prompt("clean", f"\n{mine}\n\n")
        self.assertEqual(clean, f"{mine}\n{cleanup.REPLY_FORMAT}")  # parse_reply needs the reply format: never dropped
        self.assertNotIn(cleanup.RULES[0], clean)
        self.assertEqual(cleanup.system_prompt("concise", mine), f"{mine}\n- {cleanup.CONCISE}\n{cleanup.REPLY_FORMAT}")
        body = cleanup.request_body(RAW, "clean", "local-small", mine)
        self.assertEqual(body["messages"][0]["content"], clean)
        self.assertIs(body["think"], False)
        self.assertEqual(body["response_format"], {"type": "json_object"})

    def test_polish_sends_the_custom_prompt_and_still_checks_the_reply(self):
        gw = _FakeGateway('{"text": "We should move the meeting to Wednesday. Can you send the agenda?"}')
        try:
            res = cleanup.polish(RAW, "clean", base_url=gw.url, api_key="k", model="m", prompt="My rules.")
        finally:
            gw.close()
        self.assertTrue(res.polished, res.note)
        self.assertEqual(gw.requests[0]["body"]["messages"][0]["content"], f"My rules.\n{cleanup.REPLY_FORMAT}")
        gw = _FakeGateway('{"text": "Sure! Here is a detailed agenda for Wednesday: 1. Welcome 2. Updates 3. Q&A 4. Wrap-up and next steps for everyone."}')
        try:
            res = cleanup.polish(RAW, "clean", base_url=gw.url, api_key="k", model="m", prompt="Answer questions.")
        finally:
            gw.close()
        self.assertFalse(res.polished)
        self.assertEqual(res.text, textops.strip_fillers(RAW))


class Control(unittest.TestCase):
    def test_request_rules(self):
        ok = {"Host": "127.0.0.1:8790"}
        self.assertIsNone(control.check_request("GET", "/health", ok, 8790))
        self.assertIsNone(control.check_request("POST", "/toggle", {"Host": "localhost:8790"}, 8790))
        self.assertEqual(control.check_request("GET", "/toggle", ok, 8790)[0], 405)
        self.assertEqual(control.check_request("POST", "/health", ok, 8790)[0], 405)
        self.assertEqual(control.check_request("POST", "/nope", ok, 8790)[0], 404)
        self.assertEqual(control.check_request("POST", "/toggle", {**ok, "Origin": "https://evil.example"}, 8790)[0], 403)
        self.assertEqual(control.check_request("POST", "/toggle", {"Host": "evil.example:8790"}, 8790)[0], 403)
        self.assertEqual(control.check_request("POST", "/toggle", {}, 8790)[0], 403)
        self.assertIsNone(control.check_request("POST", "/reload", ok, 8790))
        self.assertEqual(control.check_request("GET", "/reload", ok, 8790)[0], 405)

    def test_server_round_trip(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        acted: list[str] = []
        server = control.ControlServer(port, lambda: {"ok": True, "state": "idle"},
                                       lambda name: (acted.append(name), {"ok": True})[1])
        server.start()
        try:
            self.assertEqual(control.call(port, "health")["state"], "idle")
            self.assertTrue(control.call(port, "toggle")["ok"])
            self.assertEqual(acted, ["toggle"])
            import urllib.request

            req = urllib.request.Request(f"http://127.0.0.1:{port}/toggle", data=b"", method="POST",
                                         headers={"Origin": "https://example.com"})
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req, timeout=3)
            self.assertEqual(cm.exception.code, 403)
            self.assertEqual(acted, ["toggle"])
            if os.name == "nt":  # a second copy must not be able to bind the same port
                with self.assertRaises(OSError):
                    control.ControlServer(port, dict, lambda n: {})
        finally:
            server.stop()


def profile(tmp: str, media_root: str = "", native: bool = True, **dictation_keys) -> dict:
    return {
        "name": "TEST",
        "data_dir": Path(tmp) / ".run",
        "ports": {"dictation": 8790, "litellm": 4000},
        "services": {"dictation": "native" if native else "off"},
        "media": {"root": media_root, "hf_home": str(Path(tmp) / "hf")} if media_root else {},
        "agent_access": {"allowed_roots": [media_root] if media_root else []},
        "dictation": dictation_keys,
    }


class Configuration(unittest.TestCase):
    def test_defaults_and_overrides(self):
        cfg = dictation.Config.from_profile({"dictation": {"mode": "live", "silence_stop_s": "2", "button": "off"}})
        self.assertEqual((cfg.mode, cfg.silence_stop_s, cfg.button, cfg.style), ("live", 2.0, False, "clean"))

    def test_invalid_values_fall_back(self):
        cfg = dictation.Config.from_profile({"dictation": {"mode": "shout", "insert": "telepathy", "silence_stop_s": 0.1,
                                                            "phrase_pause_s": "soon"}})
        self.assertEqual((cfg.mode, cfg.insert), ("polish", "paste"))
        self.assertEqual(cfg.silence_stop_s, 0.8)      # clamped
        self.assertEqual(cfg.phrase_pause_s, 0.7)      # not a number: default

    def test_cleanup_prompt(self):
        self.assertEqual(dictation.Config.from_profile({}).cleanup_prompt, "")  # '' = the built-in prompt
        cfg = dictation.Config.from_profile({"dictation": {"cleanup_prompt": "\n  Rule one.\n\n- Rule two.\n"}})
        self.assertEqual(cfg.cleanup_prompt, "Rule one.\n\n- Rule two.")

    def test_defaults_file_matches_the_dataclass(self):
        from stacklib import profile as prof

        defaults = prof.load_defaults()
        self.assertEqual(defaults["ports"]["dictation"], 8790)
        self.assertEqual(defaults["services"]["dictation"], "off")
        cfg = dictation.Config()
        for key, value in defaults["dictation"].items():
            self.assertEqual(getattr(cfg, key), value, key)

    def test_env_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = str(Path(tmp) / "media")
            self.assertEqual(dictation.env_dir(profile(tmp, media)), Path(media) / "dictation")
            self.assertEqual(dictation.env_dir(profile(tmp)), Path(tmp) / ".run" / "dictation")
            self.assertEqual(dictation.env_dir(profile(tmp, media, env_dir=str(Path(tmp) / "x"))), Path(tmp) / "x")

    def test_service_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = str(Path(tmp) / "media")
            self.assertIsNone(dictation.service_command(profile(tmp, media, native=False), {}))
            spec = dictation.service_command(profile(tmp, media), {"LITELLM_MASTER_KEY": "sk"})
            self.assertEqual(spec["cmd"][1:], ["-P", "-m", "stacklib.dictation", "run"])
            self.assertTrue(spec["cmd"][0].startswith(str(Path(media) / "dictation" / ".venv")))
            self.assertEqual(spec["env"]["PYTHONPATH"], str(dictation.REPO / "scripts"))
            self.assertEqual(spec["env"]["HF_HOME"], str(Path(tmp) / "hf"))
            self.assertEqual(spec["env"]["AGENT_STACK_MACHINE"], "TEST")
            self.assertEqual(spec["env"]["LITELLM_MASTER_KEY"], "sk")
            self.assertFalse(dictation.installed(profile(tmp, media)))

    def test_install_refuses_folders_outside_the_allowed_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = profile(tmp, str(Path(tmp) / "media"), env_dir=str(Path(tmp) / "elsewhere"))
            with self.assertRaises(PermissionError):
                dictation.install(p)

    def test_save_setting_keeps_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            machine = Path(tmp) / "TEST.yaml"
            machine.write_text("# owner's notes\nname: TEST\nservices:\n  comfyui: native  # images\n", encoding="utf-8")
            with mock.patch("stacklib.profile.machine_file", return_value=machine):
                dictation.save_setting({"name": "TEST"}, "mode", "live")
                dictation.save_setting({"name": "TEST"}, "button", False)
            text = machine.read_text(encoding="utf-8")
            self.assertIn("# owner's notes", text)
            self.assertIn("comfyui: native  # images", text)
            self.assertIn("dictation:\n  mode: live\n  button: false", text)

    def test_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = profile(tmp)
            self.assertEqual(dictation.read_state(p), {})
            dictation.write_state(p, x=10, y=20)
            dictation.write_state(p, hidden=True)
            self.assertEqual(dictation.read_state(p), {"x": 10, "y": 20, "hidden": True})


class Integration(unittest.TestCase):
    def test_service_registration(self):
        self.assertEqual(services.SERVICE_ORDER[-1], "dictation")
        from stacklib import profile as prof

        ports = prof.load_defaults()["ports"]
        self.assertEqual(services.health_url({"ports": ports}, "dictation"), "http://127.0.0.1:8790/health")
        self.assertIn("dictation", services.EXPECTED_IMAGES)

    def test_tray_settings(self):
        ids = {settings.setting_id(s) for s in settings.SETTINGS}
        for key in ("services.dictation", "dictation.hotkey", "dictation.mode", "dictation.style", "dictation.model"):
            self.assertIn(key, ids)
        p = {"models": {}, "observability": {}, "services": {"dictation": "native"}, "ollama_env": {},
             "dictation": {"mode": "live", "silence_stop_s": 3.0, "button": True}}
        values = settings.current_values(p)
        self.assertEqual((values["services.dictation"], values["dictation.mode"]), (True, "live"))
        self.assertEqual(values["dictation.silence_stop_s"], "3.0")
        stop = next(s for s in settings.SETTINGS if settings.setting_id(s) == "dictation.silence_stop_s")
        self.assertEqual(settings._to_file_value(stop, "2.0"), 2.0)
        self.assertIn("dictation", settings.EFFECT_TEXT)
        for s in settings.SETTINGS:
            if s.section == "dictation" and s.kind == "choice":
                self.assertIn(str(values.get(settings.setting_id(s)) or s.choices[0]), s.choices + [""], s.key)

    def test_yamledit_adds_a_section(self):
        text = yamledit.set_key("name: X\n# end\n", "dictation", "hotkey", "alt+`")
        self.assertIn("dictation:\n  hotkey: alt+`", text)
        self.assertIs(settings.set_key, yamledit.set_key)

    def test_models_and_gpu_paths(self):
        self.assertEqual(models.repo_for("large-v3-turbo"), "mobiuslabsgmbh/faster-whisper-large-v3-turbo")
        self.assertEqual(models.repo_for("small"), "Systran/faster-whisper-small")
        self.assertEqual(models.repo_for("org/custom"), "org/custom")
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\x\AppData\Local", "PATH": ""}, clear=False):
            dirs = [str(d) for d in gpu.candidate_dirs(Path(r"C:\venv"))]
        self.assertIn(str(Path(r"C:\Users\x\AppData\Local") / "Programs" / "Ollama" / "lib" / "ollama" / "cuda_v12"), dirs)
        self.assertEqual(dirs[0], str(Path(r"C:\venv") / "Lib" / "site-packages" / "nvidia" / "cublas" / "bin"))


class MultiLineYaml(unittest.TestCase):
    """yamledit writes the cleanup prompt as a literal block and replaces a value that spans lines whole."""

    def test_blocks_round_trip_and_keep_the_rest_of_the_file(self):
        base = ("# owner's notes\nname: TEST\ndictation:\n  language: en               # set by me\n"
                "  cleanup_prompt: ''         # '' = built-in\n                             # a continued comment\n"
                "  button: true\nservices:\n  dictation: native\n")
        first = "You turn raw speech.\n- Keep 'quotes' and # signs.\n\n- ไทย and émoji 🎤."
        text = yamledit.set_key(base, "dictation", "cleanup_prompt", first)
        # The continued comment would become part of the block, so both comment lines move above the key.
        self.assertIn("  # '' = built-in\n  # a continued comment\n  cleanup_prompt: |-\n    You turn raw speech.\n", text)
        for value in (first, "Second\n  indented line\nlast", "  starts with spaces\nnext", "a space \nand\ta tab", ""):
            text = yamledit.set_key(text, "dictation", "cleanup_prompt", value)
            data = yaml.safe_load(text)
            self.assertEqual(data["dictation"], {"language": "en", "cleanup_prompt": value, "button": True}, repr(value))
            self.assertEqual(data["services"], {"dictation": "native"})
        self.assertIn("# owner's notes", text)
        self.assertIn("  language: en               # set by me", text)
        text = yamledit.set_key(text, "dictation", "button", False)
        self.assertEqual(text.count("button:"), 1)

    def test_hand_written_multi_line_values_are_replaced_whole(self):
        folded = "dictation:\n  cleanup_prompt: >-   # mine\n    folded text\n    continues here\n\n  mic: ''\n"
        self.assertEqual(yamledit.set_key(folded, "dictation", "cleanup_prompt", "A\nB"),
                         "dictation:\n  cleanup_prompt: |-   # mine\n    A\n    B\n\n  mic: ''\n")
        quoted = 'dictation:\n  cleanup_prompt: "first\n    second # not a comment"\n  mic: x\n'
        self.assertEqual(yamledit.set_key(quoted, "dictation", "cleanup_prompt", "one # two"),
                         "dictation:\n  cleanup_prompt: 'one # two'\n  mic: x\n")

    def test_keys_next_to_a_block_and_values_with_hash_signs(self):
        block = "dictation:\n  cleanup_prompt: |-\n    a\n    b\n"
        self.assertEqual(yaml.safe_load(yamledit.set_key(block, "dictation", "language", "th"))["dictation"],
                         {"cleanup_prompt": "a\nb", "language": "th"})
        # A '#' inside a value used to hide the key, so a second `vocabulary:` line was appended.
        self.assertEqual(yamledit.set_key("dictation:\n  vocabulary: C#, F#\n  mic: ''\n", "dictation", "vocabulary", "Rust"),
                         "dictation:\n  vocabulary: Rust\n  mic: ''\n")


class CleanupPromptSetting(unittest.TestCase):
    """The tray's Voice typing > Advanced > Cleanup prompt."""

    def setUp(self):
        self.s = next(s for s in settings.SETTINGS if settings.setting_id(s) == "dictation.cleanup_prompt")
        self.p = {"name": "TEST", "models": {}, "observability": {}, "services": {"dictation": "native"},
                  "ollama_env": {}, "ports": {"dictation": 8790}, "dictation": {"cleanup_prompt": ""}}

    def test_the_box_shows_the_built_in_prompt_and_saves_only_a_change(self):
        self.assertEqual((self.s.kind, self.s.advanced, self.s.effect), ("text", True, "dictation"))
        sid = "dictation.cleanup_prompt"
        self.assertEqual(settings.current_values(self.p)[sid], cleanup.DEFAULT_PROMPT)
        for box in (cleanup.DEFAULT_PROMPT, cleanup.DEFAULT_PROMPT.replace("\n", "  \r\n") + "\n\n", "", " \n "):
            self.assertEqual(settings.changed(self.p, {sid: box}), [], repr(box[:30]))
            self.assertEqual(settings._to_file_value(self.s, box), "")  # the built-in text stays in the code
        mine = "Clean it.\n- Keep my words."
        self.assertEqual(settings.changed(self.p, {sid: mine + "  \n"}), [self.s])
        self.assertEqual(settings._to_file_value(self.s, "\n" + mine.replace("\n", " \r\n") + "\n"), mine)
        custom = {**self.p, "dictation": {"cleanup_prompt": mine}}
        self.assertEqual(settings.current_values(custom)[sid], mine)
        self.assertEqual(settings.changed(custom, {sid: cleanup.DEFAULT_PROMPT}), [self.s])

    def test_save_writes_a_block_and_restore_default_writes_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            machine = Path(tmp) / "TEST.yaml"
            machine.write_text("# notes\nname: TEST\ndictation:\n  language: en               # chosen\n", encoding="utf-8")
            mine = "Clean it.\n\n- Keep 'quotes', # signs and ไทย."
            with mock.patch("stacklib.profile.machine_file", return_value=machine):
                self.assertEqual(settings.save(self.p, {"dictation.cleanup_prompt": mine}), [self.s])
                text = machine.read_text(encoding="utf-8")
                self.assertIn("  cleanup_prompt: |-\n    Clean it.\n\n    - Keep 'quotes', # signs and ไทย.\n", text)
                self.assertIn("  language: en               # chosen", text)
                saved = {**self.p, "dictation": {"cleanup_prompt": mine}}
                self.assertEqual(settings.save(saved, {"dictation.cleanup_prompt": cleanup.DEFAULT_PROMPT}), [self.s])
            self.assertEqual(yaml.safe_load(machine.read_text(encoding="utf-8"))["dictation"],
                             {"language": "en", "cleanup_prompt": ""})

    def test_the_running_app_takes_a_new_prompt_without_a_restart(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        acted: list[str] = []
        server = control.ControlServer(port, dict, lambda name: (acted.append(name), {"ok": True})[1])
        server.start()
        p = {**self.p, "ports": {"dictation": port}, "dictation": {"cleanup_prompt": "Mine."}}
        logs: list[str] = []
        try:
            self.assertTrue(settings._update_dictation(p, {"cleanup_prompt"}, logs.append))
            with mock.patch.object(control, "ACTIONS", ("toggle", "show", "hide")):  # an app from before /reload
                self.assertFalse(settings._update_dictation(p, {"cleanup_prompt"}, logs.append))
        finally:
            server.stop()
        self.assertEqual(acted, ["reload"])
        self.assertEqual(logs, ["Voice typing uses your own cleanup prompt from the next dictation"])
        self.assertTrue(settings._update_dictation(p, {"cleanup_prompt"}, logs.append))  # not running: read at start
        style = next(s for s in settings.SETTINGS if settings.setting_id(s) == "dictation.style")
        self.assertEqual(settings.effect_texts([self.s]), ["update voice typing (no restart)"])
        self.assertEqual(settings.effect_texts([self.s, style]), ["restart voice typing"])

    def test_apply_restarts_voice_typing_only_for_other_settings(self):
        from stacklib import profile as prof

        with tempfile.TemporaryDirectory() as tmp:
            machine = Path(tmp) / "TEST.yaml"
            machine.write_text("name: TEST\nservices:\n  dictation: native\n", encoding="utf-8")
            with mock.patch("stacklib.profile.machine_file", return_value=machine), \
                    mock.patch.object(services, "_task_managed", return_value=set()), \
                    mock.patch.object(services, "stop") as stop, \
                    mock.patch.object(services, "start", return_value={}) as start, \
                    mock.patch.object(control, "call", return_value={"ok": True}) as call:
                p = settings.apply(prof.resolve_profile("TEST"), {"dictation.cleanup_prompt": "Mine."}, log=lambda m: None)
                call.assert_called_once_with(p["ports"]["dictation"], "reload")
                stop.assert_not_called()
                start.assert_not_called()
                self.assertEqual(p["dictation"]["cleanup_prompt"], "Mine.")
                settings.apply(p, {"dictation.style": "concise"}, log=lambda m: None)
                stop.assert_called_once()
                start.assert_called_once()


class Languages(unittest.TestCase):
    def test_every_whisper_language_is_offered(self):
        self.assertEqual(len(models.WHISPER_LANGUAGES), 100)
        for code in ("en", "zh", "jw", "haw", "yue"):
            self.assertIn(code, models.WHISPER_LANGUAGES)
        codes = [code for code, _ in models.LANGUAGES]
        self.assertEqual(codes[0], "auto")
        self.assertEqual(sorted(codes[1:]), sorted(models.WHISPER_LANGUAGES))
        names = [name for _, name in models.LANGUAGES[1:]]
        self.assertEqual(names, sorted(names))
        self.assertEqual(len(set(names)), len(names))
        for code in models.ALIASES:
            self.assertTrue(code == "auto" or code in models.WHISPER_LANGUAGES, code)

    def test_matches_the_installed_faster_whisper(self):
        try:
            from faster_whisper.tokenizer import _LANGUAGE_CODES
        except ImportError:
            self.skipTest("faster-whisper is not installed in this environment (it is in the voice typing one)")
        self.assertEqual(set(models.WHISPER_LANGUAGES), set(_LANGUAGE_CODES))

    def test_search(self):
        def codes(q):
            return [c for c, _ in models.search(q)]

        self.assertEqual(codes(""), [c for c, _ in models.LANGUAGES])
        self.assertEqual(codes("en")[0], "en")             # the exact code first
        self.assertIn("hy", codes("en"))                   # then names containing it (Armenian)
        self.assertEqual(codes("ch")[0], "zh")             # a name that starts with it before ones containing it
        self.assertEqual(codes("NOR"), ["no", "nn"])       # case-insensitive
        self.assertEqual(codes("bokmal"), ["no"])          # other names, accents ignored
        self.assertEqual(codes("farsi"), ["fa"])
        self.assertEqual(codes("jv"), ["jw"])
        self.assertEqual(codes("detect"), ["auto"])
        self.assertEqual(codes("  port "), ["pt"])
        self.assertEqual(codes("zzz"), [])
        self.assertEqual(models.search("ital", [("it", "Italian"), ("de", "German")]), [("it", "Italian")])

    def test_english_only_models(self):
        for model in ("small.en", "medium.en", "distil-large-v3.5", "distil-whisper/distil-large-v3.5-ct2"):
            self.assertEqual(models.languages_for(model), [models.AUTO, ("en", "English")], model)
        self.assertEqual(len(models.languages_for("large-v3-turbo")), 101)

    def test_names_and_validation(self):
        self.assertEqual(models.language_name("en"), "English")
        self.assertEqual(models.language_name("auto"), "Detect automatically")
        self.assertEqual(models.language_name("xx"), "xx")
        cfg = dictation.Config.from_profile({"dictation": {"language": "EN"}})
        self.assertEqual(cfg.language, "en")
        with mock.patch("stacklib.dictation.warn") as warned:
            cfg = dictation.Config.from_profile({"dictation": {"language": "english"}})
        self.assertEqual(cfg.language, "auto")
        warned.assert_called_once()

    def test_tray_setting_searches_all_languages(self):
        s = next(s for s in settings.SETTINGS if settings.setting_id(s) == "dictation.language")
        self.assertEqual(s.kind, "search")
        self.assertEqual(s.choices[0], "auto")
        self.assertEqual(len(s.choices), 101)
        self.assertEqual(s.labels["en"], "English")
        values = settings.current_values({"models": {}, "observability": {}, "services": {}, "ollama_env": {},
                                          "dictation": {"language": "pt"}})
        self.assertEqual(values["dictation.language"], "pt")
        self.assertEqual(settings._to_file_value(s, "pt"), "pt")


if __name__ == "__main__":
    unittest.main()
