"""Tests for scripts/stacklib/whisper.py (what is left of recordings: folders, and taking the server out of Claude
Desktop's config, since the stack no longer sets it up) and scripts/whisper_mcp.py (path guard, transcript files).
Nothing here loads a model or touches the real Claude Desktop config."""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import profile as prof, whisper  # noqa: E402


def make_profile(root: str, allowed: list[str] | None = None) -> dict:
    return {"media": prof.resolve_media({"whisper_model": "large-v3-turbo", "whisper_compute": "int8_float16"},
                                        {"root": root, "hf_home": root + "\\hf"}),
            "agent_access": {"allowed_roots": [root] if allowed is None else allowed}}


class Profile(unittest.TestCase):
    def test_folders_default_below_the_root(self):
        m = make_profile("D:\\media")["media"]
        self.assertEqual(m["whisper_dir"], "D:\\media\\whisper")
        self.assertEqual(m["recordings_dir"], "D:\\media\\inputs\\recordings")
        self.assertEqual(m["transcripts_dir"], "D:\\media\\outputs\\transcripts")


class Desktop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = Path(self.tmp.name) / "Claude" / "claude_desktop_config.json"
        self.p = make_profile("D:\\media")

    def tearDown(self):
        self.tmp.cleanup()

    def test_unregister_removes_only_ours_and_reads_a_byte_order_mark(self):
        self.config.parent.mkdir(parents=True)
        data = {"mcpServers": {"other": {"command": "x"}, "local-whisper": {"command": "y"}}, "theme": "dark"}
        self.config.write_text(json.dumps(data), encoding="utf-8-sig")   # saved by an editor that adds a BOM
        self.assertIn("removed", whisper.unregister_desktop(self.config))
        left = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual((left["mcpServers"], left["theme"]), ({"other": {"command": "x"}}, "dark"))
        self.assertEqual(len(list(self.config.parent.glob("*.bak-*"))), 1)
        self.assertIn("not registered", whisper.unregister_desktop(self.config))

    def test_nothing_sets_the_server_up_any_more(self):
        for name in ("install", "register_desktop", "server_entry"):
            self.assertFalse(hasattr(whisper, name), name)


class Server(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "rec"
        self.root.mkdir()
        os.environ.update({"WHISPER_ROOTS": str(self.root), "WHISPER_RECORDINGS": str(self.root),
                           "WHISPER_TRANSCRIPTS": str(Path(self.tmp.name) / "out")})
        sys.modules.pop("whisper_mcp", None)
        self.srv = importlib.import_module("whisper_mcp")

    def tearDown(self):
        for k in ("WHISPER_ROOTS", "WHISPER_RECORDINGS", "WHISPER_TRANSCRIPTS"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def test_guard(self):
        self.assertTrue(self.srv.allowed(str(self.root / "a.wav")))
        self.assertFalse(self.srv.allowed(str(self.root / ".." / "secret.wav")))
        self.assertFalse(self.srv.allowed("relative.wav"))
        self.assertIn("error", self.srv.transcribe_recording(str(Path(self.tmp.name) / "outside.wav")))

    def test_outputs_keep_the_cache_key_and_timestamps(self):
        audio = self.root / "meeting.m4a"
        audio.write_bytes(b"x")
        key = self.srv.cache_key(str(audio), None, None)
        base = self.srv.out_base(str(audio), key)
        result = {"language": "en", "language_probability": 0.99, "duration_s": 3725.0, "elapsed_s": 1.0,
                  "model": "test", "segments": [{"start": 0.0, "end": 2.5, "text": "Hello."},
                                                {"start": 3661.2, "end": 3663.0, "text": "Bye."}]}
        files = self.srv.write_outputs(str(audio), base, result)
        self.assertTrue(files["markdown"].endswith(f"meeting.{key}.md"))
        md = Path(files["markdown"]).read_text(encoding="utf-8")
        self.assertIn("[00:00] Hello.", md)
        self.assertIn("[1:01:01] Bye.", md)
        self.assertIn("01:01:01,200 --> 01:01:03,000", Path(files["srt"]).read_text(encoding="utf-8"))
        listed = self.srv.list_recordings()["recordings"]
        self.assertEqual([(Path(r["path"]).name, r["transcribed"]) for r in listed], [("meeting.m4a", True)])

    def test_long_transcripts_are_paged(self):
        segs = [{"start": float(i), "end": i + 1.0, "text": "word " * 50} for i in range(250)]   # ~64k chars: two pages
        job = {"job_id": "j", "status": "done", "result": {"language": "en", "segments": segs}}
        first = self.srv.reply(job)
        self.assertEqual(len(first["transcript"]), self.srv.PAGE)
        rest = self.srv.reply(job, first["next_offset"])
        self.assertNotIn("next_offset", rest)
        self.assertEqual(first["transcript"] + rest["transcript"], self.srv.as_text(job["result"]))


if __name__ == "__main__":
    unittest.main()
