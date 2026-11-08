"""Tests for the voice typing history (scripts/stacklib/dictation/voicelog.py and history.VoiceHistoryWindow): what you
dictated is kept for dictation.keep_minutes, the mic menu's "last text" reads the newest kept entry, the window lists
and acts on entries, and the tray setting reaches the running app without a restart. App itself imports numpy, which
the project environment lacks, so these test the pieces it is built from.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import settings  # noqa: E402
from stacklib.dictation import Config, control, refine  # noqa: E402
from stacklib.dictation.voicelog import VOICE_LOG_NAME, VoiceLog  # noqa: E402

HEARD = "um so the release is uh delayed until thursday"
TYPED = "The release is delayed until Thursday."


def _entry(**kw) -> dict:
    return {"kind": "dictation", "mode": "polish", "style": "clean", "app": "notepad.exe", "window": "Untitled",
            "before": HEARD, "after": TYPED, "status": "inserted", "note": "", "seconds": 4.2, **kw}


class KeepMinutes(unittest.TestCase):
    def test_default_and_limits(self):
        self.assertEqual(Config.from_profile({}).keep_minutes, 30.0)
        self.assertEqual(Config.from_profile({"dictation": {"keep_minutes": "15"}}).keep_minutes, 15.0)
        self.assertEqual(Config.from_profile({"dictation": {"keep_minutes": 0}}).keep_minutes, 1.0)
        self.assertEqual(Config.from_profile({"dictation": {"keep_minutes": 99999}}).keep_minutes, 43200.0)

    def test_defaults_file_documents_it(self):
        import yaml

        defaults = yaml.safe_load((Path(__file__).resolve().parents[1] / "machines" / "_defaults.yaml")
                                  .read_text(encoding="utf-8"))
        self.assertEqual(defaults["dictation"]["keep_minutes"], 30)

    def test_log_name_is_its_own_file(self):
        from stacklib.dictation.refinelog import LOG_NAME

        self.assertNotEqual(VOICE_LOG_NAME, LOG_NAME)


class Log(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = [1_800_000_000.0]
        self.log = VoiceLog(Path(self.tmp.name) / VOICE_LOG_NAME, keep_minutes=30, clock=lambda: self.now[0])

    def test_last_is_the_newest_kept_dictation(self):
        self.assertIsNone(self.log.last())
        self.log.append(_entry(after="First."))
        self.now[0] += 60
        second = self.log.append(_entry(after="Second."))
        self.now[0] += 60
        self.log.append(_entry(after="", status="failed"))           # nothing to paste again
        self.assertEqual(self.log.last()["id"], second["id"])

    def test_entries_expire_and_the_file_goes(self):
        self.log.append(_entry())
        self.now[0] += 29 * 60
        self.assertIsNotNone(self.log.last())
        self.now[0] += 2 * 60                                         # 31 minutes old
        self.assertIsNone(self.log.last())
        self.assertEqual(self.log.prune(), 1)
        self.assertFalse(self.log.path.exists())

    def test_a_shorter_window_applies_at_once(self):
        self.log.append(_entry())
        self.now[0] += 10 * 60
        self.log.keep_minutes = 5                                     # the tray lowered dictation.keep_minutes
        self.assertEqual(self.log.entries(), [])
        self.assertEqual(self.log.prune(), 1)

    def test_the_text_stays_on_this_machine_only_in_the_file(self):
        self.log.append(_entry())
        text = self.log.path.read_text(encoding="utf-8")
        self.assertIn(HEARD, text)
        self.assertIn(TYPED, text)


class Setting(unittest.TestCase):
    def _setting(self):
        return next(s for s in settings.SETTINGS if settings.setting_id(s) == "dictation.keep_minutes")

    def test_choices_and_file_value(self):
        keep = self._setting()
        self.assertEqual((keep.effect, settings._to_file_value(keep, "60")), ("dictation", 60))
        self.assertIn(str(int(Config().keep_minutes)), keep.choices)
        values = settings.current_values({"models": {}, "observability": {}, "services": {}, "ollama_env": {},
                                          "dictation": {"keep_minutes": 30}, "refine": {}})
        self.assertEqual(values["dictation.keep_minutes"], "30")

    def test_applies_without_a_restart(self):
        keep = self._setting()
        self.assertEqual(settings.effect_texts([keep]), ["update voice typing (no restart)"])
        new = {"name": "T", "services": {"dictation": "native"}, "ports": {"dictation": 8790},
               "dictation": {"keep_minutes": 15}, "refine": {}}
        with mock.patch.object(settings, "save", return_value=[keep]), \
                mock.patch.object(settings.prof, "resolve_profile", return_value=new), \
                mock.patch.object(settings.services, "_task_managed", return_value=set()), \
                mock.patch.object(settings.services, "stop") as stop, \
                mock.patch.object(settings.services, "start") as start, \
                mock.patch.object(control, "call", return_value={"ok": True}) as call:
            settings.apply({"name": "T"}, {"dictation.keep_minutes": "15"}, log=lambda m: None)
        call.assert_called_once_with(8790, "reload")
        stop.assert_not_called()
        start.assert_not_called()


def _tk():
    try:
        import tkinter as tk

        root = tk.Tk()
    except Exception:  # noqa: BLE001 - no Tk or no display
        return None
    root.withdraw()
    return root


class Window(unittest.TestCase):
    """The real window, never shown, over a fake app."""

    @classmethod
    def setUpClass(cls):
        cls.root = _tk()   # one root for the class: Tk refuses a new interpreter after a few destroyed ones

    @classmethod
    def tearDownClass(cls):
        if cls.root is not None:
            cls.root.destroy()

    def setUp(self):
        if self.root is None:
            self.skipTest("no Tk")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        log = VoiceLog(Path(self.tmp.name) / VOICE_LOG_NAME, keep_minutes=30)
        self.app = SimpleNamespace(voice_log=log, voice_keep_text=lambda: refine.keep_text(30),
                                   paste_text=mock.Mock(), copy_text=mock.Mock())

    def _open(self):
        from stacklib.dictation.history import HistoryWindow, VoiceHistoryWindow

        with mock.patch.object(VoiceHistoryWindow, "_tick"):
            w = VoiceHistoryWindow(self.root, self.app)
        w.win.withdraw()
        self.addCleanup(w.close)
        self.assertIsNone(HistoryWindow._open)                       # the refine window's slot is untouched
        return w

    def test_empty(self):
        w = self._open()
        self.assertEqual(w.win.title(), "Voice typing history")
        self.assertIn("Nothing dictated in the last 30 minutes", w.list.get(0))
        self.assertEqual(str(w.again_button["state"]), "disabled")

    def test_lists_shows_and_acts_on_an_entry(self):
        self.app.voice_log.append(_entry())
        w = self._open()
        self.assertIn("notepad", w.list.get(0))
        self.assertIn(TYPED, w.list.get(0))
        self.assertEqual(w.before.get("1.0", "end-1c"), HEARD)
        self.assertEqual(w.after.get("1.0", "end-1c"), TYPED)
        self.assertEqual((w.before_label["text"], w.after_label["text"]), ("Heard (Whisper)", "Typed"))
        self.assertIn("4.2 s of speech, clean cleanup", w.detail["text"])
        w._copy("before")
        self.app.copy_text.assert_called_once_with(HEARD)
        w._again()
        self.app.paste_text.assert_called_once_with(TYPED)

    def test_text_not_typed_is_labelled(self):
        self.app.voice_log.append(_entry(status="copied", mode="live"))
        w = self._open()
        self.assertEqual(w.after_label["text"], "Text (not typed)")
        self.assertIn("typed as you spoke", w.detail["text"])


if __name__ == "__main__":
    unittest.main()
