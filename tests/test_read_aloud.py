"""Tests for reading selected text aloud (scripts/stacklib/dictation: speak, reader, player, and the read aloud parts of
the app, the tray, the installer's feature list and the usage registry). Nothing here plays sound, presses keys, reads
the real clipboard or loads Kokoro: the flow runs against a fake app window, a fake voice and the WAV-file player.
"""
from __future__ import annotations

import ast
import inspect
import tempfile
import threading
import time
import unittest
import wave
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

import yaml

from stacklib import features, install, settings, usage
from stacklib import profile as prof
from stacklib.dictation import control, hotkey, selection, speak
from stacklib.dictation.player import FilePlayer
from stacklib.dictation.reader import Reader
from test_refine import FakeClip, FakeWin, RecordingUI

REPO = Path(__file__).resolve().parents[1]
ARTICLE = ("## Release notes\n"
           "- Fixed the **login** bug, see https://github.com/example/repo/pull/12 for details.\n"
           "- Dr. Smith reviewed [[Project Apollo]] on 3 May.\n"
           "id:: 6543a1b2-1234-4567-89ab-0123456789ab\n\n"
           "The quick brown fox jumps over the lazy dog. It was a bright cold day in April. Did it work? Yes!")


def voice(vid: str) -> speak.Voice:
    return speak.kokoro_voice(vid)


ZIRA = speak.Voice("windows:Microsoft Zira", "Zira", "en-us", "windows", "female", "HKEY_LOCAL_MACHINE\\x")
PATTARA = speak.Voice("windows:Microsoft Pattara", "Pattara", "th-th", "windows", "male", "HKEY_LOCAL_MACHINE\\y")
ALL = [*speak.kokoro_voices(), ZIRA]


# ---------------------------------------------------------------- settings and voices

class Configuration(unittest.TestCase):
    def test_defaults_match_the_profile_defaults(self):
        defaults = prof.load_defaults()["read_aloud"]
        cfg = speak.Config.from_profile({"read_aloud": defaults})
        self.assertEqual((cfg.enabled, cfg.hotkey, cfg.voice, cfg.speed, cfg.kokoro), (False, "ctrl+alt+s", "af_heart",
                                                                                         1.0, "fp32"))
        self.assertEqual(speak.Config(), cfg)

    def test_bad_values_fall_back_and_numbers_are_clamped(self):
        warned = []
        cfg = speak.Config.from_profile({"read_aloud": {"speed": 9, "kokoro": "fp64", "max_chars": 5,
                                                        "unload_after_min": "x", "voices": "fr", "enabled": "yes",
                                                        "voice": ""}}, warn=warned.append)
        self.assertEqual((cfg.speed, cfg.kokoro, cfg.max_chars, cfg.unload_after_min, cfg.voices, cfg.enabled,
                          cfg.voice), (2.0, "fp32", 200, 30.0, {}, True, "af_heart"))
        self.assertEqual(len(warned), 3)   # kokoro, unload_after_min, voices
        self.assertEqual(speak.Config.from_profile({"read_aloud": {"speed": 0.1}}).speed, 0.5)

    def test_voices_mapping_is_merged_from_the_machine_file(self):
        merged = prof.resolve_read_aloud({"voice": "af_heart", "voices": {"fr": "ff_siwis"}},
                                         {"voice": "bf_emma", "voices": {"de": "windows:Microsoft Katja"}})
        self.assertEqual(merged["voices"], {"fr": "ff_siwis", "de": "windows:Microsoft Katja"})
        cfg = speak.Config.from_profile({"read_aloud": {"voices": {"DE ": " windows:Microsoft Katja "}}})
        self.assertEqual(cfg.voices, {"de": "windows:Microsoft Katja"})

    def test_kokoro_catalog(self):
        for vid in speak.KOKORO_VOICE_IDS:
            v = speak.kokoro_voice(vid)
            self.assertIsNotNone(v, vid)
            self.assertIn(v.gender, ("female", "male"))
        self.assertEqual(speak.kokoro_voice("af_heart").label, "Heart (US English, female)")
        self.assertEqual(speak.kokoro_voice("ff_siwis").language, "fr-fr")
        self.assertIsNone(speak.kokoro_voice("jf_alpha"))   # Japanese needs Kokoro's own G2P, not espeak-ng
        self.assertTrue(set(speak.DEFAULT_FOR_LANGUAGE.values()) <= set(speak.KOKORO_VOICE_IDS))
        self.assertEqual(ZIRA.label, "Zira (US English, female, Windows)")

    def test_voice_choices_list_kokoro_then_windows(self):
        choices = speak.voice_choices([ZIRA])
        self.assertEqual(choices[0], ("af_heart", "Heart (US English, female)"))
        self.assertEqual(choices[-1][0], "windows:Microsoft Zira")

    def test_small_helpers(self):
        self.assertEqual([speak.sapi_rate(s) for s in (1.0, 3.0, 1 / 3, 2.0, 0.5, 0, float("nan"))],
                         [0, 10, -10, 6, -6, 0, 0])
        self.assertEqual(speak.speed_text(1.0), "1x")
        self.assertEqual(speak.speed_text(1.25), "1.25x")
        self.assertEqual(speak.seconds_text(59.6), "1 min 00 s")
        self.assertEqual(speak.seconds_text(125), "2 min 05 s")
        self.assertEqual(speak.lcid_tag("409;9"), "en-us")
        self.assertEqual(speak.lcid_tag("41E"), "th-th")
        self.assertEqual(speak.lcid_tag("nope"), "")
        self.assertEqual(speak.family("pt-br"), "pt")


# ---------------------------------------------------------------- text for listening

class SpeechText(unittest.TestCase):
    def test_markup_goes_and_every_line_ends_in_punctuation(self):
        lines = speak.speech_text(ARTICLE).split("\n")
        self.assertEqual(lines[:3], ["Release notes.", "Fixed the login bug, see github.com for details.",
                                     "Dr. Smith reviewed Project Apollo on 3 May."])
        self.assertEqual(lines[3], "")   # the paragraph break stays; the Logseq property is gone
        self.assertTrue(lines[4].startswith("The quick brown fox"))
        self.assertNotIn("id::", speak.speech_text(ARTICLE))

    def test_more_markup(self):
        cases = {
            "| Name | Cost |\n|---|---|\n| Server | 12 |": "Name, Cost.\nServer, 12.",
            "> quoted *text* and `code` and ~~gone~~ stays": "quoted text and code and gone stays.",
            "[the docs](https://example.com/a(b)) and ![a chart](x.png)": "the docs and a chart.",
            "((6543a1b2-1234-4567-89ab-0123456789ab)) {{embed [[x]]}} see #project-plan": "see project plan.",
            "```python\nprint('hi')\n```": "print('hi').",
            "snake_case_name stays, 2*3*4 too": "snake_case_name stays, 2*3*4 too.",
            "Line one\r\nLine two\x0bLine three\u2028Four": "Line one.\nLine two.\nLine three.\nFour.",
            "- [ ] buy milk\n- [x] done": "buy milk.\ndone.",
            "---\n***": "",
            "   \n\n  ": "",
        }
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(speak.speech_text(raw), want)

    def test_cut_ends_at_a_sentence(self):
        text = "One two three. " * 40
        out = speak.cut(text, 100)
        self.assertLessEqual(len(out), 100)
        self.assertTrue(out.endswith("."))
        self.assertEqual(speak.cut("short", 100), "short")


class Pieces(unittest.TestCase):
    def test_sentences_skip_abbreviations_initials_and_decimals(self):
        s = speak.sentences("Mr. J. R. Smith paid 3.5 dollars at 10 a.m. sharp! Did he? Yes. See e.g. the notes.")
        self.assertEqual(s, ["Mr. J. R. Smith paid 3.5 dollars at 10 a.m. sharp!", "Did he?", "Yes.",
                             "See e.g. the notes."])
        self.assertEqual(speak.sentences("你好。今天很好！"), ["你好。", "今天很好！"])

    def test_first_piece_is_one_short_sentence_then_pieces_grow(self):
        text = " ".join(f"This is sentence number {i} of a long paragraph that keeps going." for i in range(12))
        parts = speak.pieces(text)
        self.assertEqual(parts[0].text, "This is sentence number 0 of a long paragraph that keeps going.")
        self.assertGreater(len(parts[1].text), len(parts[0].text) * 2)
        self.assertTrue(all(len(p.text) <= speak.PIECE_CHARS for p in parts))
        self.assertEqual([p.paragraph_end for p in parts], [False] * (len(parts) - 1) + [True])
        self.assertEqual(" ".join(p.text for p in parts), text)

    def test_long_sentences_are_split_at_commas_then_words(self):
        clause = "and then the committee discussed the budget at great length"
        text = "Opening line. " + ", ".join([clause] * 12) + "."
        parts = speak.pieces(text)
        self.assertTrue(all(len(p.text) <= speak.HARD_CHARS for p in parts), [len(p.text) for p in parts])
        words = "x" * 30 + " " + " ".join(["word"] * 200)
        self.assertTrue(all(len(p.text) <= speak.FIRST_CHARS for p in speak.pieces(words)[:1]))

    def test_paragraphs_and_list_items_are_their_own_pieces(self):
        parts = speak.pieces(speak.speech_text(ARTICLE))
        self.assertEqual(parts[0], speak.Piece("Release notes.", True))
        self.assertTrue(all(p.paragraph_end for p in parts[:3]))


# ---------------------------------------------------------------- language and voice

class Languages(unittest.TestCase):
    def test_detect(self):
        cases = {
            "This is plain English text that should be detected as such by the detector.": ["en"],
            "Bonjour, je suis très content de vous voir aujourd'hui et nous allons parler de la musique.": ["fr"],
            "El perro come la comida que está en la mesa y no quiere salir de la casa.": ["es"],
            "Der Hund ist nicht in dem Haus und die Katze ist auch nicht da.": ["de"],
            "Il gatto è sulla sedia e non vuole scendere perché è molto stanco della giornata.": ["it"],
            "สวัสดีครับ ยินดีต้อนรับ": ["th"],
            "नमस्ते आप कैसे हैं": ["hi"],
            "日本語のテキストです": ["ja"],
            "这是中文文本": ["zh", "ja"],
            "Привет, как дела?": ["ru", "uk", "bg"],
            "ok": [],
            "12345 !!!": [],
            "Meeting at 10, room B": [],   # too short and too plain to tell
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(speak.detect_languages(text), want)

    def test_the_chosen_voice_reads_its_own_language(self):
        cfg = speak.Config()
        self.assertEqual(speak.pick_voice(cfg, "Hello there, this is English and it is plain to see.", ALL),
                         (voice("af_heart"), ""))

    def test_other_languages_get_their_voice(self):
        cfg = speak.Config()
        v, note = speak.pick_voice(cfg, "Bonjour, je suis très content de vous voir et nous allons parler.", ALL)
        self.assertEqual((v.id, note), ("ff_siwis", "The text is in French, so Siwis reads it."))
        v, note = speak.pick_voice(cfg, "สวัสดีครับ ยินดีต้อนรับ", [*ALL, PATTARA])
        self.assertEqual(v.id, "windows:Microsoft Pattara")
        cfg.voices = {"fr": "windows:Microsoft Zira"}
        self.assertEqual(speak.pick_voice(cfg, "Bonjour, je suis très content de vous voir et nous allons.", ALL)[0],
                         ZIRA)

    def test_no_voice_for_the_language_says_how_to_add_one(self):
        v, note = speak.pick_voice(speak.Config(), "สวัสดีครับ ยินดีต้อนรับ", ALL)
        self.assertEqual(v.id, "af_heart")
        self.assertIn("No Thai voice is installed", note)
        self.assertIn("Time & language > Speech", note)

    def test_auto_language_off(self):
        cfg = speak.Config(auto_language=False)
        self.assertEqual(speak.pick_voice(cfg, "Bonjour, je suis très content de vous voir et nous allons.", ALL),
                         (voice("af_heart"), ""))

    def test_a_missing_voice_falls_back_to_one_of_its_language(self):
        v, note = speak.pick_voice(speak.Config(voice="bf_emma"), "Hello there, plain English text it is.", [ZIRA])
        self.assertEqual(v, ZIRA)
        self.assertEqual(note, "Emma is not available, so Zira reads it.")
        self.assertEqual(speak.pick_voice(speak.Config(), "text", []), (None, ""))


class Phonemes(unittest.TestCase):
    def test_text_for_espeak(self):
        self.assertEqual(speak.for_phonemes("Dr. Smith paid $1,234.50 (cash) for items 3-5.", "en-us"),
                         "Doctor Smith paid 1234 dollars and 50 cents «cash» for items 3 to 5.")
        self.assertEqual(speak.for_phonemes("It cost £1 and €2.05.", "en-gb"),
                         "It cost 1 pound and 2 euros and 5 cents.")
        self.assertEqual(speak.for_phonemes("Il a payé $5 (3-5).", "fr-fr"), "Il a payé $5 «3-5».")   # English only

    def test_punctuation_is_kept_between_the_words(self):
        self.assertEqual(speak.split_punctuation("Hello, world! How are you?"),
                         [(False, "Hello"), (True, ", "), (False, "world"), (True, "! "), (False, "How are you"),
                          (True, "?")])

    def test_tidy_and_tokens(self):
        self.assertEqual(speak.tidy_phonemes("(fr)bɔ̃ʒuʁ(en) rˈɛd", "en-us"), "bɔ̃ʒuʁ ɹˈɛd")
        self.assertEqual(speak.tidy_phonemes("nˈaɪnti", "en-us"), "nˈaɪndi")
        self.assertEqual(speak.tidy_phonemes("nˈaɪnti", "en-gb"), "nˈaɪnti")
        vocab = {" ": 16, "a": 43, "b": 44, ".": 4}
        self.assertEqual(speak.token_ids("ab. x", vocab), [43, 44, 4, 16])

    def test_long_phoneme_strings_are_split_at_spaces(self):
        vocab = {" ": 1, "a": 2}
        runs = speak.split_ids(" ".join(["aaaa"] * 300), vocab, limit=100)
        self.assertTrue(all(len(r) <= 100 for r in runs))
        self.assertEqual(sum(len(r) for r in runs), 300 * 4 + 299 - (len(runs) - 1))   # a space lost per cut
        self.assertTrue(all(r[0] == 2 and r[-1] == 2 for r in runs))


# ---------------------------------------------------------------- the player that writes a file

class Players(unittest.TestCase):
    def test_file_player_writes_every_piece_and_reports_each_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.wav"
            started = []
            p = FilePlayer(str(out), 24000, started.append, pace=0)
            p.start()
            p.play(bytes(4800), 0)
            p.play(bytes(2400), 1)
            p.finish()
            self.assertTrue(p.wait(5))
            self.assertEqual(started, [0, 1])
            with wave.open(str(out)) as w:
                self.assertEqual((w.getframerate(), w.getnframes()), (24000, 3600))

    def test_stop_ends_it_early(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = FilePlayer(str(Path(tmp) / "o.wav"), 24000, None, pace=1.0)
            p.start()
            p.play(bytes(48000 * 10), 0)   # ten seconds
            time.sleep(0.1)
            p.stop()
            self.assertTrue(p.wait(2))


# ---------------------------------------------------------------- the whole flow, with fakes

@dataclass
class FakeAudio:
    pcm: bytes
    seconds: float
    tokens: int = 10
    run_s: float = 0.01
    load_s: float = 0.0


class ReadUI(RecordingUI):
    def __getattr__(self, kind):
        if kind in ("speaking", "paused"):
            return lambda title, body="", hint="": self.calls.append((kind, title, hint))
        if kind == "progress":
            return lambda fraction: self.calls.append(("progress", fraction, ""))
        return super().__getattr__(kind)


class Flow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.win = FakeWin(selected=ARTICLE, app="logseq.exe")
        self.clip = FakeClip(self.win)
        self.ui = ReadUI()
        self.esc: list[bool] = []
        self.cfg = speak.Config(enabled=True)
        self.voices = list(ALL)
        self.spoken: list[tuple[str, str]] = []
        self.records: list[dict] = []
        self.gate: threading.Event | None = None
        self.error: Exception | None = None
        self.busy_reason = ""
        self.pace = 0.0
        self.players: list[FilePlayer] = []
        self.missing = ""
        self.reader = Reader(call=lambda fn: fn(self.win, self.clip), target=lambda: 100, ui=self.ui,
                             cfg=lambda: self.cfg, voices=lambda cfg: self.voices, synth=self.synth,
                             player=self.player, esc=self.esc.append, busy_elsewhere=lambda: self.busy_reason,
                             record=lambda v, c, **kw: self.records.append({"voice": v.id, **kw}),
                             hotkey_text=lambda: "Ctrl+Alt+S", missing=lambda cfg: self.missing)
        patcher = mock.patch("stacklib.dictation.reader.capture", side_effect=lambda ws, clip, target, elevated, purpose:
                             selection.capture(ws, clip, target, elevated=elevated, copy_wait=0.05, purpose=purpose))
        patcher.start()
        self.addCleanup(patcher.stop)

    def synth(self, text, v, speed, cfg):
        self.spoken.append((text, v.id))
        if self.error is not None and v.engine == "kokoro":
            raise self.error
        if self.gate is not None and len(self.spoken) == 2:
            self.gate.wait(5)
        return FakeAudio(bytes(2 * 240), 0.01)

    def player(self, on_start):
        p = FilePlayer(str(Path(self.tmp.name) / f"p{len(self.players)}.wav"), 24000, on_start, pace=self.pace)
        self.players.append(p)
        return p

    def wait(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and (self.reader.busy or any(
                t.name == "read-aloud" for t in threading.enumerate())):
            time.sleep(0.01)
        self.assertFalse(self.reader.busy)
        for p in self.players:   # the WAV file is closed before the temporary folder goes
            self.assertTrue(p.wait(5))

    def test_reads_the_selection_and_puts_the_clipboard_back(self):
        self.assertTrue(self.reader.start("test"))
        self.wait()
        texts = [t for t, _ in self.spoken]
        self.assertEqual(texts, [p.text for p in speak.pieces(speak.speech_text(ARTICLE))])
        self.assertEqual({v for _, v in self.spoken}, {"af_heart"})
        self.assertEqual(self.win.board["text"], "what you copied earlier")
        self.assertEqual(self.ui.last("done"), "Finished reading")
        self.assertIn("Reading with Heart (1 of", next(t for k, t, _ in self.ui.calls if k == "speaking"))
        self.assertIn("Ctrl+Alt+S or Esc stops", next(h for k, _t, h in self.ui.calls if k == "speaking"))
        self.assertEqual(self.esc, [True, False])
        [rec] = self.records
        self.assertEqual((rec["voice"], rec["stopped"], rec["failed"], rec["tokens"]),
                         ("af_heart", False, "", 10 * len(texts)))
        self.assertEqual(self.reader.last_text, speak.speech_text(ARTICLE))

    def test_stop_while_it_reads(self):
        self.gate = threading.Event()
        self.reader.start()
        deadline = time.monotonic() + 5
        while len(self.spoken) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(self.reader.stop())
        self.gate.set()
        self.wait()
        self.assertEqual(self.ui.last("cancelled"), "Stopped reading")
        self.assertEqual(self.ui.last("done"), "")
        self.assertEqual(len(self.spoken), 2)   # nothing more was prepared
        self.assertTrue(self.records[0]["stopped"])
        self.assertEqual(self.esc, [True, False])

    def test_the_hotkey_toggles_and_a_click_resumes_a_pause(self):
        self.pace = 0.05   # slow playback, so it is still reading
        self.reader.start()
        deadline = time.monotonic() + 5
        while not (self.players and self.reader.job and self.reader.job.index >= 0) and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(self.reader.pause())
        self.assertTrue(self.reader.paused)
        self.assertEqual(self.ui.last("paused"), "Paused")
        self.assertTrue(self.reader.toggle("button"))   # a click on the button while paused: go on
        self.assertFalse(self.reader.paused)
        self.assertTrue(self.reader.toggle("hotkey"))   # the hotkey while reading: stop
        self.wait()
        self.assertEqual(self.ui.last("cancelled"), "Stopped reading")

    def _concurrency(self, delay: float):
        """A fake voice that notes how many pieces are being made at once."""
        live, peak, lock = [0], [0], threading.Lock()

        def slow(text, v, speed, cfg):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(delay)
            with lock:
                live[0] -= 1
            self.spoken.append((text, v.id))
            return FakeAudio(bytes(2 * 240), 0.01)
        return slow, peak

    def test_later_pieces_are_made_in_parallel_and_played_in_order(self):
        self.reader.synth, peak = self._concurrency(0.05)
        self.reader.workers = lambda v: 2
        self.win.selected = " ".join(f"Sentence number {i} is here." for i in range(12))
        started = []
        make = self.player
        self.reader.player = lambda on_start: make(lambda tag: (started.append(tag), on_start(tag)))
        self.reader.start()
        self.wait()
        n = len(speak.pieces(speak.speech_text(self.win.selected)))
        self.assertGreater(n, 3)
        self.assertEqual(started, list(range(n)))          # every piece, in order
        self.assertEqual(peak[0], 2)                        # two made at once
        self.assertEqual(self.ui.last("done"), "Finished reading")

    def test_a_busy_pc_gets_one_piece_at_a_time(self):
        self.reader.synth, peak = self._concurrency(0.03)
        self.reader.workers = lambda v: 3
        self.reader.pc_busy = lambda: True
        self.win.selected = " ".join(f"Sentence number {i} is here." for i in range(10))
        self.reader.start()
        self.wait()
        self.assertEqual(peak[0], 1)
        self.assertEqual(self.ui.last("done"), "Finished reading")

    def test_lookahead_limits_what_is_made_ahead(self):
        self.pace = 1.0                                     # real-time playback: 0.5 s per piece
        made = []

        def half_second(text, v, speed, cfg):
            made.append(text)
            return FakeAudio(bytes(2 * 12000), 0.5)
        self.reader.synth = half_second
        self.reader.workers = lambda v: 2
        self.reader.lookahead_s = lambda v: 1.0
        self.win.selected = " ".join(f"Sentence number {i} is here." for i in range(40))
        self.reader.start()
        time.sleep(1.0)
        self.assertLess(len(made), 8)                       # many pieces, but only about 1 s of speech ahead
        self.reader.stop()
        self.wait()

    def test_a_later_piece_that_fails_stops_there(self):
        calls = []

        def flaky(text, v, speed, cfg):
            calls.append(text)
            if len(calls) == 3:
                raise RuntimeError("the GPU went away")
            return FakeAudio(bytes(2 * 240), 0.01)
        self.reader.synth = flaky
        self.win.selected = " ".join(f"Sentence number {i} is here." for i in range(8))
        self.reader.start()
        self.wait()
        self.assertEqual(self.ui.last("error"), "Could not read it aloud")
        self.assertEqual(self.records[0]["failed"], "RuntimeError")
        self.assertEqual(len(calls), 3)

    def test_the_voice_loads_while_the_selection_is_copied(self):
        warmed = []
        self.reader.warm = lambda cfg: warmed.append(cfg.voice)
        self.reader.start()
        self.wait()
        self.assertEqual(warmed, ["af_heart"])

    def test_nothing_selected(self):
        self.win.selected = ""
        self.reader.start()
        self.wait()
        self.assertEqual(self.ui.last("error"), "Nothing selected")
        self.assertEqual((self.spoken, self.records, self.esc), ([], [], []))

    def test_pictures_and_tables_do_not_stop_a_reading(self):
        self.win = FakeWin(selected="A caption under a chart.", html="<!--StartFragment--><img src=x>A caption"
                                                                     "<!--EndFragment-->")
        self.clip = FakeClip(self.win)
        self.reader.start()
        self.wait()
        self.assertEqual(self.spoken, [("A caption under a chart.", "af_heart")])

    def test_terminals_are_refused_with_read_aloud_wording(self):
        self.win.app = "windowsterminal.exe"
        self.reader.start()
        self.wait()
        self.assertEqual(self.ui.last("error"), "Read aloud does not work in a terminal")
        self.assertEqual(self.win.copies, 0)

    def test_not_installed(self):
        self.voices = []
        self.missing = "Read aloud is not installed. Tick Read aloud in the installer."
        self.reader.start()
        self.wait()
        self.assertEqual(self.ui.last("error"), "Read aloud is not installed")
        self.assertEqual(self.ui.hint("error"), self.missing)
        self.assertEqual(self.spoken, [])

    def test_a_kokoro_failure_falls_back_to_a_windows_voice(self):
        self.error = RuntimeError("Kokoro could not load: espeak-ng did not load")
        self.reader.start()
        self.wait()
        self.assertEqual(self.spoken[0][1], "af_heart")
        self.assertEqual({v for _, v in self.spoken[1:]}, {"windows:Microsoft Zira"})
        self.assertIn("Zira (a Windows voice) reads it instead", next(h for k, _t, h in self.ui.calls
                                                                      if k == "speaking"))
        self.assertEqual(self.ui.last("done"), "Finished reading")

    def test_a_failure_without_a_fallback_stops_with_a_message(self):
        self.error = RuntimeError("Kokoro could not load")
        self.voices = speak.kokoro_voices()
        self.reader.start()
        self.wait()
        self.assertEqual(self.ui.last("error"), "Could not read it aloud")
        self.assertEqual(self.records[0]["failed"], "RuntimeError")

    def test_waits_while_dictating(self):
        self.busy_reason = "Finish dictating first"
        self.assertFalse(self.reader.start())
        self.assertEqual(self.ui.last("note"), "Finish dictating first")

    def test_again_and_sample_need_no_selection(self):
        self.reader.start()
        self.wait()
        self.win.selected = ""
        n = len(self.spoken)
        self.assertTrue(self.reader.again("menu"))
        self.wait()
        self.assertEqual(len(self.spoken), n)                 # replayed from memory
        self.assertEqual(self.ui.last("done"), "Finished reading")
        self.reader.sample("bm_george", "George")
        self.wait()
        self.assertEqual(self.spoken[-1][1], "bm_george")
        self.assertEqual(self.ui.last("done"), "Voice: George")
        self.assertEqual(self.reader.last_text, speak.speech_text(ARTICLE))   # a sample is not "the last text"

    def test_again_replays_the_kept_audio_without_the_model(self):
        self.reader.start()
        self.wait()
        n, records = len(self.spoken), len(self.records)
        self.assertTrue(self.reader.again("menu"))
        self.wait()
        self.assertEqual(len(self.spoken), n)                 # nothing made again
        self.assertEqual(len(self.records), records)          # no model ran, so no usage record
        self.assertIn("replayed", self.ui.hint("done"))
        with wave.open(str(Path(self.tmp.name) / "p1.wav")) as w:
            self.assertGreater(w.getnframes(), 0)               # and it played
        self.cfg.speed = 1.5                                   # another speed: made again
        self.reader.again("menu")
        self.wait()
        self.assertEqual(len(self.spoken), 2 * n)

    def test_again_after_a_stop_makes_only_what_is_missing(self):
        self.gate = threading.Event()
        self.reader.start()
        deadline = time.monotonic() + 5
        while len(self.spoken) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.reader.stop()
        self.gate.set()
        self.wait()
        self.gate = None
        before = len(self.spoken)
        total = len(speak.pieces(speak.speech_text(ARTICLE)))
        self.reader.again("menu")
        self.wait()
        self.assertEqual(len(self.spoken) - before, total - 2)  # the two made before the stop are replayed

    def test_again_with_nothing_read_yet(self):
        self.assertFalse(self.reader.again())
        self.assertEqual(self.ui.last("note"), "Nothing read yet")

    def test_esc_can_be_left_to_other_apps(self):
        self.cfg.esc_stops = False
        self.reader.start()
        self.wait()
        self.assertEqual(self.esc, [])
        self.assertIn("Ctrl+Alt+S stops", next(h for k, _t, h in self.ui.calls if k == "speaking"))

    def test_long_text_is_cut_with_a_note(self):
        self.cfg.max_chars = 200
        self.win.selected = "A sentence that is not short at all. " * 30
        self.reader.start()
        self.wait()
        self.assertLessEqual(sum(len(t) + 1 for t, _ in self.spoken), 201)
        self.assertIn("Only the first 200 characters are read.", self.ui.hint("done"))

    def test_language_switch_note(self):
        self.win.selected = "Bonjour, je suis très content de vous voir aujourd'hui et nous allons parler de la musique."
        self.reader.start()
        self.wait()
        self.assertEqual(self.spoken[0][1], "ff_siwis")
        self.assertIn("The text is in French, so Siwis reads it.", self.ui.hint("done"))


# ---------------------------------------------------------------- wiring: app, tray, installer, usage

class Wiring(unittest.TestCase):
    BASE = REPO / "scripts" / "stacklib" / "dictation"

    def test_control_actions(self):
        ok = {"Host": "127.0.0.1:8790"}
        for name in ("read", "read_stop", "read_pause", "show_read", "hide_read"):
            self.assertIsNone(control.check_request("POST", f"/{name}", ok, 8790), name)
            self.assertEqual(control.check_request("GET", f"/{name}", ok, 8790)[0], 405, name)

    def test_hotkey_choices(self):
        for choice in hotkey.READ_CHOICES:
            hotkey.parse(choice)
        self.assertEqual(hotkey.READ_CHOICES[0], speak.Config().hotkey)
        d = prof.load_defaults()
        taken = {hotkey.parse(k) for k in (d["dictation"]["hotkey"], d["refine"]["hotkey"], d["refine"]["menu_hotkey"])}
        self.assertEqual([c for c in hotkey.READ_CHOICES if hotkey.parse(c) in taken], [])

    def test_button_order(self):
        tree = ast.parse((self.BASE / "overlay.py").read_text(encoding="utf-8"))
        buttons = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                       and getattr(n.targets[0], "id", "") == "BUTTONS")
        self.assertEqual(buttons, ("refine", "mic", "read"))   # pencil, mic, speaker from left to right

    def test_reader_is_built_with_its_own_arguments(self):
        tree = ast.parse((self.BASE / "app.py").read_text(encoding="utf-8"))
        call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Reader")
        accepted = set(inspect.signature(Reader.__init__).parameters) - {"self"}
        self.assertEqual({k.arg for k in call.keywords} - accepted, set())

    def test_when_off_the_app_takes_no_hotkey(self):
        src = (self.BASE / "app.py").read_text(encoding="utf-8")
        self.assertIn('if self.scfg.enabled:   # an optional feature', src)
        self.assertIn("show_read=self.scfg.enabled and self.scfg.button", src)

    def test_tray_settings(self):
        ids = {settings.setting_id(s) for s in settings.SETTINGS if s.section == "read_aloud"}
        self.assertEqual(ids, {"read_aloud.enabled", "read_aloud.hotkey", "read_aloud.voice", "read_aloud.speed",
                               "read_aloud.auto_language", "read_aloud.button", "read_aloud.esc_stops",
                               "read_aloud.kokoro", "read_aloud.device"})
        p = {"models": {}, "observability": {}, "services": {}, "ollama_env": {}, "dictation": {}, "refine": {},
             "read_aloud": {"speed": 1.25, "voice": "bf_emma", "enabled": True}}
        values = settings.current_values(p)
        self.assertEqual((values["read_aloud.speed"], values["read_aloud.voice"], values["read_aloud.enabled"]),
                         ("1.25", "bf_emma", True))
        speed = next(s for s in settings.SETTINGS if settings.setting_id(s) == "read_aloud.speed")
        self.assertEqual(settings._to_file_value(speed, "1.5"), 1.5)
        voice_setting = next(s for s in settings.SETTINGS if settings.setting_id(s) == "read_aloud.voice")
        self.assertIn("af_heart", voice_setting.choices)
        self.assertFalse(voice_setting.show_code)

    def _apply(self, sid: str, value, read: dict):
        setting = next(s for s in settings.SETTINGS if settings.setting_id(s) == sid)
        new = {"name": "T", "services": {"dictation": "native"}, "ports": {"dictation": 8790}, "dictation": {},
               "refine": {}, "read_aloud": read}
        with mock.patch.object(settings, "save", return_value=[setting]), \
                mock.patch.object(settings.prof, "resolve_profile", return_value=new), \
                mock.patch.object(settings.services, "_task_managed", return_value=set()), \
                mock.patch.object(settings.services, "stop") as stop, \
                mock.patch.object(settings.services, "start", return_value={}) as start, \
                mock.patch.object(control, "call", return_value={"ok": True}) as call:
            settings.apply({"name": "T"}, {sid: value}, log=lambda m: None)
        return stop, start, call

    def test_the_button_toggles_without_a_restart(self):
        stop, _start, call = self._apply("read_aloud.button", False, {"button": False, "enabled": True})
        call.assert_called_once_with(8790, "hide_read")
        stop.assert_not_called()

    def test_the_button_setting_while_read_aloud_is_off_restarts_nothing(self):
        stop, start, call = self._apply("read_aloud.button", True, {"button": True, "enabled": False})
        call.assert_not_called()
        stop.assert_not_called()
        start.assert_not_called()

    def test_voice_and_speed_need_no_restart_but_the_switch_and_hotkey_do(self):
        for sid in ("read_aloud.voice", "read_aloud.speed", "read_aloud.auto_language", "read_aloud.kokoro",
                    "read_aloud.device"):
            stop, start, call = self._apply(sid, "x", {})
            stop.assert_not_called()
            start.assert_not_called()
            call.assert_not_called()
        for sid in ("read_aloud.enabled", "read_aloud.hotkey"):
            stop, start, _call = self._apply(sid, "x", {})
            stop.assert_called_once()
            start.assert_called_once()

    def test_usage_source(self):
        self.assertEqual(usage.SOURCES["read-aloud"].kinds, ("speech",))
        self.assertIn("read-aloud", usage.SERVICE_MODELS["dictation"])

    def test_gpu_card_lists_kokoro_on_the_cpu(self):
        from stacklib import gpu_models

        health = {"engine": "unloaded", "read_aloud": {"engine": "ready", "model": "kokoro-82m fp32",
                                                       "unload_after_min": 30, "idle_s": 120}}
        [row] = gpu_models.rows([], health)
        self.assertEqual((row["name"], row["by"], row["gpu"], row["bytes"], row["unloads"]),
                         ("kokoro-82m fp32", "Read aloud", "CPU", 0, "in 28 min"))
        self.assertEqual(gpu_models.rows([], {"read_aloud": {"engine": "unloaded"}}), [])

    def test_the_tray_hides_the_speaker_controls_while_read_aloud_is_off(self):
        src = (REPO / "scripts" / "tray.py").read_text(encoding="utf-8")
        self.assertIn('read.get("enabled", True)', src)
        self.assertIn('("Read aloud", "read_aloud")', src)


class Feature(unittest.TestCase):
    def test_it_is_optional_and_needs_voice_typing(self):
        f = features.BY_ID["read_aloud"]
        self.assertFalse(f.required)
        self.assertEqual(f.requires, ("voice_typing",))
        self.assertEqual(features.with_requirements({"read_aloud"}), {"read_aloud", "voice_typing"})
        self.assertEqual(features.dependents("voice_typing"), ["read_aloud"])
        self.assertIn("read_aloud", install.chosen_with_required({"read_aloud"}))
        self.assertIn("voice_typing", install.chosen_with_required({"read_aloud"}))
        self.assertFalse(features.RECOMMENDED["read_aloud"](features.Hardware()))
        self.assertIn(("read_aloud", "Install read aloud (Kokoro voices)"), [(s, t) for s, t, _ in install.STEPS])

    def test_estimate_follows_the_weights(self):
        hw = features.Hardware(vram_gb=12, desktop_vram_gb=1, ram_gb=32, threads=12)
        with mock.patch.object(features, "_kokoro_cached", return_value=False):
            fp32 = features.estimate("read_aloud", {"read_aloud": {"kokoro": "fp32", "device": "cpu"}}, hw)
            int8 = features.estimate("read_aloud", {"read_aloud": {"kokoro": "int8"}}, hw)
            off = features.estimate("read_aloud", {"read_aloud": {"kokoro": "off"}}, hw)
            on_gpu = features.estimate("read_aloud", {"read_aloud": {"kokoro": "fp32", "device": "auto"}}, hw)
            no_card = features.estimate("read_aloud", {"read_aloud": {"device": "gpu"}}, features.Hardware(threads=12))
        self.assertEqual((on_gpu.vram_gb, on_gpu.cpu_bursts), (1.0, False))
        self.assertAlmostEqual(on_gpu.disk_gb, fp32.disk_gb + features.KOKORO_GPU_GB)
        self.assertEqual((no_card.vram_gb, no_card.ram_gb), (0.0, 0.5))   # no GPU: the CPU estimate
        self.assertEqual((fp32.ram_gb, int8.ram_gb, off.ram_gb), (0.5, 0.3, 0.05))
        self.assertGreater(fp32.disk_gb, int8.disk_gb)
        self.assertEqual((fp32.vram_gb, fp32.cpu_bursts), (0.0, True))
        est = {f.id: features.Estimate() for f in features.FEATURES} | {"read_aloud": fp32}
        found = features.assess(["read_aloud"], est, hw)
        self.assertTrue(any(x.level == "ok" and "read aloud uses about 6 of 12" in x.text for x in found))

    def test_status(self):
        with mock.patch("stacklib.dictation.read_aloud_installed", return_value=True):
            on = features._status_read_aloud({"read_aloud": {"enabled": True}})
            off = features._status_read_aloud({"read_aloud": {"enabled": False}})
        self.assertEqual((on.state, off.state), ("Installed", "Installed, off"))
        self.assertIn("Ctrl+Alt+S", on.detail)
        with mock.patch("stacklib.dictation.read_aloud_installed", return_value=False):
            self.assertEqual(features._status_read_aloud({"read_aloud": {"enabled": True}}).state, "Not installed")

    def test_install_step_skips_when_not_chosen(self):
        with self.assertRaises(install.Skip):
            install.step_read_aloud(None, {"read_aloud": {"enabled": False}, "services": {"dictation": "native"}}, print)
        with self.assertRaises(install.Skip):
            install.step_read_aloud(None, {"read_aloud": {"enabled": True}, "services": {"dictation": "off"}}, print)
        with mock.patch("stacklib.dictation.install_read_aloud", return_value="done") as run:
            self.assertEqual(install.step_read_aloud(None, {"read_aloud": {"enabled": True},
                                                            "services": {"dictation": "native"}}, print), "done")
        run.assert_called_once()

    def test_choosing_it_turns_on_voice_typing_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "T.yaml"
            path.write_text("name: T\n# keep me\nservices:\n  dictation: 'off'\n", encoding="utf-8")
            profile = {"name": "T", "services": {"dictation": "off"}, "observability": {},
                       "read_aloud": {"enabled": False}}
            status = {f.id: features.Status(False, False, "Not installed", "") for f in features.FEATURES}
            with mock.patch.object(install.prof, "machine_file", return_value=path):
                install.save_features(profile, {"read_aloud"}, status=status)
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(doc["services"]["dictation"], "native")
        self.assertIs(doc["read_aloud"]["enabled"], True)

    def test_installed_needs_the_packages_and_the_weights(self):
        from stacklib import dictation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = {"dictation": {"env_dir": str(root / "env")}, "media": {"hf_home": str(root / "hf")},
                       "read_aloud": {"kokoro": "fp32"}}
            site = root / "env" / ".venv" / "Lib" / "site-packages"
            with mock.patch.object(dictation, "installed", return_value=True), \
                    mock.patch.object(dictation, "IS_WINDOWS", True):
                self.assertFalse(dictation.read_aloud_installed(profile))
                for pkg in ("espeakng_loader", "comtypes"):
                    (site / pkg).mkdir(parents=True)
                    (site / pkg / "__init__.py").write_text("", encoding="utf-8")
                self.assertFalse(dictation.read_aloud_installed(profile))   # the weights are missing
                snap = (root / "hf" / "hub" / "models--onnx-community--Kokoro-82M-v1.0-ONNX" / "snapshots"
                        / speak.KOKORO_REVISION)
                for name in ("onnx/model.onnx", "tokenizer.json", "voices/af_heart.bin"):
                    (snap / name).parent.mkdir(parents=True, exist_ok=True)
                    (snap / name).write_bytes(b"x")
                self.assertTrue(dictation.read_aloud_installed(profile))
                self.assertFalse(dictation.kokoro_cached(profile, "int8"))
                self.assertTrue(dictation.read_aloud_installed({**profile, "read_aloud": {"kokoro": "off"}}))


class KokoroRow(unittest.TestCase):
    """The tray's Kokoro row shows read aloud while the standalone Kokoro service is off."""

    def row(self, health, enabled=True, status=None):
        return features.read_aloud_row({"read_aloud": {"enabled": enabled}}, health, status)[:2]

    def test_states(self):
        installed = features.Status(True, True, "Installed", "")
        missing = features.Status(False, False, "Not installed", "")

        def ra(**kw):
            return {"read_aloud": {"enabled": True, "engine": "unloaded", **kw}}
        self.assertEqual(self.row(None, enabled=False, status=missing), ("off", "Not installed"))
        self.assertEqual(self.row(None, enabled=False), ("off", "Read aloud off"))
        self.assertEqual(self.row(None, status=missing), ("warn", "Not installed"))
        self.assertEqual(self.row(None, status=installed), ("off", "Starts with voice typing"))
        self.assertEqual(self.row({"read_aloud": {"enabled": False}}), ("warn", "Restart voice typing"))
        self.assertEqual(self.row(ra()), ("good", "Ready (loads when used)"))
        self.assertEqual(self.row(ra(engine="ready", device="cuda")), ("good", "Loaded on the GPU"))
        self.assertEqual(self.row(ra(engine="ready", device="cpu", busy=True)), ("good", "Reading (CPU)"))
        self.assertEqual(self.row(ra(engine="ready", busy=True, paused=True)), ("good", "Paused"))
        self.assertEqual(self.row(ra(engine="loading")), ("warn", "Loading"))
        self.assertEqual(self.row(ra(engine="failed"))[0], "bad")

    def test_the_speaker_button_sits_on_the_kokoro_row(self):
        tree = ast.parse((REPO / "scripts" / "tray.py").read_text(encoding="utf-8"))
        build = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_build_overview")
        branches = [n for n in ast.walk(build) if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
                    and any(isinstance(c, ast.Constant) and c.value == "kokoro" for c in n.test.comparators)]
        self.assertTrue(any("read_btn" in ast.unparse(b) for b in branches))
        dictation = [n for n in ast.walk(build) if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
                     and any(isinstance(c, ast.Constant) and c.value == "dictation" for c in n.test.comparators)]
        self.assertFalse(any("read_btn" in ast.unparse(b) for b in dictation))

    def test_gpu_card_row_on_cuda(self):
        from stacklib import gpu_models

        [row] = gpu_models.rows([], {"read_aloud": {"engine": "ready", "device": "cuda", "model": "kokoro-82m fp32"}})
        self.assertEqual((row["gpu"], row["bytes"]), ("100%", int(gpu_models.KOKORO_GPU * gpu_models.GIB)))


class Gpu(unittest.TestCase):
    def test_device_setting(self):
        self.assertEqual(speak.Config().device, "auto")
        warned = []
        self.assertEqual(speak.Config.from_profile({"read_aloud": {"device": "TPU"}}, warn=warned.append).device, "auto")
        self.assertEqual(len(warned), 1)
        self.assertEqual(speak.Config.from_profile({"read_aloud": {"device": "GPU"}}).device, "gpu")

    def test_cuda_dirs_need_cudnn_and_ollamas_cuda_13(self):
        from stacklib.dictation import gpu

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cudnn = root / "venv" / "Lib" / "site-packages" / "nvidia" / "cudnn" / "bin"
            ollama = root / "local" / "Programs" / "Ollama" / "lib" / "ollama" / "cuda_v13"
            cudnn.mkdir(parents=True)
            ollama.mkdir(parents=True)
            (cudnn / "cudnn64_9.dll").write_bytes(b"")
            with mock.patch.dict("os.environ", {"LOCALAPPDATA": str(root / "local"), "PATH": ""}):
                self.assertEqual(gpu.kokoro_cuda_dirs(root / "venv"), [])     # no CUDA 13 runtime yet
                (ollama / "cudart64_13.dll").write_bytes(b"")
                (ollama / "cublas64_13.dll").write_bytes(b"")
                self.assertEqual(gpu.kokoro_cuda_dirs(root / "venv"), [cudnn, ollama])

    def test_gpu_install_choice(self):
        from stacklib import dictation

        with mock.patch.object(dictation, "which", return_value=None):
            self.assertTrue(dictation.wants_gpu({"read_aloud": {"device": "gpu"}}))
            self.assertFalse(dictation.wants_gpu({"read_aloud": {"device": "cpu"}}))
            self.assertFalse(dictation.wants_gpu({"read_aloud": {"device": "auto"}}))
            self.assertTrue(dictation.wants_gpu({"read_aloud": {"device": "auto"}, "detected": {"vram_mib": 12288}}))
        with mock.patch.object(dictation, "which", return_value="C:/Windows/System32/nvidia-smi.exe"):
            self.assertTrue(dictation.wants_gpu({"read_aloud": {}}))

    def test_voice_typing_install_keeps_the_gpu_runtime(self):
        from stacklib import dictation

        with tempfile.TemporaryDirectory() as tmp:
            profile = {"dictation": {"env_dir": tmp}}
            site = Path(tmp) / ".venv" / "Lib" / "site-packages"
            (site / "onnxruntime_gpu-1.31.1.dist-info").mkdir(parents=True)
            (site / "nvidia" / "cudnn" / "bin").mkdir(parents=True)
            (site / "nvidia" / "cudnn" / "bin" / "cudnn64_9.dll").write_bytes(b"")
            with mock.patch.object(dictation, "IS_WINDOWS", True):
                self.assertTrue(dictation.read_aloud_gpu_installed(profile))
        self.assertTrue(dictation.READ_GPU_PACKAGES[0].startswith("onnxruntime-gpu=="))
        src = (REPO / "scripts" / "stacklib" / "dictation" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('READ_GPU_PACKAGES[0] if pkg.startswith("onnxruntime==") and read_aloud_gpu_installed(profile)',
                      src)


if __name__ == "__main__":
    unittest.main()
