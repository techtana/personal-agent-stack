"""Read aloud's Mandarin voices: Kokoro v1.1-zh from config/installer.yaml kokoro_zh (stacklib/dictation/speak.py and
tts.py), installed and removed through the setup worker like the Piper voices (dictation, install.py, uninstall.py),
counted by the features estimate, the Storage card and the GPU card. Nothing here downloads, installs or deletes
anything outside a temporary folder, and nothing loads a model.

The Engine class at the end needs numpy and misaki (voice typing's environment); run it there by hand:
    C:/media/dictation/.venv/Scripts/python.exe -m unittest test_kokoro_zh   (with PYTHONPATH=scripts;tests)

Checked by hand on 2026-11-08 in read aloud's environment: 100 voices ranked by a Whisper round trip, speed and memory
measured, and a test copy of the app read a Chinese selection from a Win32 EDIT window with Voice 003, which Whisper
transcribed back word for word (memory/state.md).
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from stacklib import catalog, dictation, features, gpu_models, install, settings, storage, uninstall  # noqa: E402
from stacklib.dictation import speak  # noqa: E402

ZH = catalog.section("kokoro_zh")
HUIHUI = speak.Voice("windows:Microsoft Huihui", "Huihui", "zh-cn", "windows", "female", "HKEY_LOCAL_MACHINE\\z")


def fake_zh_files(hf: Path, variants=("fp32",), voices=None) -> Path:
    """The Mandarin model's snapshot folder in a fake Hugging Face cache, with tiny stand-ins for its files."""
    snap = hf / "hub" / f"models--{speak.ZH_REPO.replace('/', '--')}" / "snapshots" / speak.ZH_REVISION
    names = {"tokenizer.json", *(speak.ZH_FILES[v] for v in variants),
             *(f"voices/{v}.bin" for v in (speak.ZH_VOICES if voices is None else voices))}
    for name in names:
        (snap / name).parent.mkdir(parents=True, exist_ok=True)
        (snap / name).write_bytes(b"x" * 1000)
    return snap


def fake_packages(site: Path, modules=dictation.ZH_MODULES) -> None:
    for m in modules:
        (site / m).mkdir(parents=True, exist_ok=True)
        (site / m / "__init__.py").write_text("", encoding="utf-8")


class Catalog(unittest.TestCase):
    def test_pinned_open_and_complete(self):
        self.assertRegex(ZH["revision"], r"^[0-9a-f]{40}$")
        self.assertEqual(ZH["repo"], "onnx-community/Kokoro-82M-v1.1-zh-ONNX")
        self.assertEqual(ZH["licence"], "Apache-2.0")
        self.assertEqual(set(speak.ZH_FILES), {"fp32", "int8"})   # read_aloud.kokoro's choices
        for v in ZH["variants"].values():
            self.assertRegex(v["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(v["download_mb"], 100)
        self.assertTrue(all(p.count("==") == 1 for p in speak.ZH_PACKAGES))   # every package pinned
        self.assertIn("misaki", {p.split("==")[0] for p in speak.ZH_PACKAGES})
        self.assertTrue(set(dictation.ZH_MODULES) <= {p.split("==")[0].replace("-", "_") for p in speak.ZH_PACKAGES})

    def test_voices_are_mandarin_ids_with_their_gender(self):
        self.assertGreaterEqual(len(speak.ZH_VOICES), 4)
        for vid, gender in speak.ZH_VOICES.items():
            with self.subTest(voice=vid):
                self.assertRegex(vid, r"^z[fm]_\d{3}$")
                self.assertEqual(gender, {"f": "female", "m": "male"}[vid[1]])
        self.assertEqual({g for g in speak.ZH_VOICES.values()}, {"female", "male"})
        self.assertNotIn("zf_001", speak.ZH_VOICES)   # upstream's sample voice came last in the Whisper check


class Voices(unittest.TestCase):
    def test_ids_names_and_labels(self):
        first = next(iter(speak.ZH_VOICES))
        v = speak.zh_voice(f"kokoro-zh:{first}")
        self.assertEqual((v.engine, v.language, v.family), ("kokoro-zh", "zh-cn", "zh"))
        self.assertEqual(v.label, f"Voice {first[3:]} (Chinese, Mandarin, female)")
        self.assertIsNone(speak.zh_voice("kokoro-zh:zf_999"))
        self.assertIsNone(speak.zh_voice(first))              # the prefix names the model
        self.assertIsNone(speak.kokoro_voice(f"kokoro-zh:{first}"))
        self.assertEqual(speak.known_voice(f"kokoro-zh:{first}"), v)
        self.assertEqual(speak.DEFAULT_FOR_LANGUAGE["zh"], f"kokoro-zh:{first}")
        self.assertEqual([x.id for x in speak.zh_voices()], [f"kokoro-zh:{k}" for k in speak.ZH_VOICES])

    def test_choices_list_them_only_when_downloaded(self):
        ids = [vid for vid, _ in speak.voice_choices([], packs_dir="")]
        self.assertFalse(any(i.startswith("kokoro-zh:") for i in ids))
        ids = [vid for vid, _ in speak.voice_choices([], packs_dir="", zh=True)]
        self.assertEqual(sum(i.startswith("kokoro-zh:") for i in ids), len(speak.ZH_VOICES))
        self.assertLess(ids.index("af_heart"), ids.index(speak.DEFAULT_FOR_LANGUAGE["zh"]))

    def test_a_voice_set_beside_the_piper_voices(self):
        self.assertEqual(speak.PACK_KEYS[-2:], ("kokoro-zh", "kokoro-th"))   # after the Piper voices; Thai last
        self.assertEqual(speak.pack_language("kokoro-zh"), "zh-cn")
        self.assertEqual(speak.pack_title("kokoro-zh"), f"Chinese, Mandarin: {len(speak.ZH_VOICES)} Kokoro voices")
        self.assertEqual(speak.pack_title("de_DE-thorsten-high"), "German: Thorsten")
        voices_mb = speak.ZH_VOICE_MB * len(speak.ZH_VOICES)
        self.assertAlmostEqual(speak.pack_size_mb("kokoro-zh", "int8"), ZH["variants"]["int8"]["download_mb"] + voices_mb)
        self.assertAlmostEqual(speak.pack_size_mb("kokoro-zh", "off"), ZH["variants"]["fp32"]["download_mb"] + voices_mb)
        self.assertAlmostEqual(speak.pack_disk_mb("kokoro-zh"), speak.pack_size_mb("kokoro-zh") + ZH["packages_mb"])
        self.assertEqual(speak.pack_disk_mb("de_DE-thorsten-high"), 114)
        self.assertIn("LongMaoData", speak.pack_note("kokoro-zh"))
        self.assertIn("research-only", speak.pack_note("de_DE-thorsten-high"))

    def test_settings_accept_it(self):
        warned = []
        cfg = speak.Config.from_profile({"read_aloud": {"packs": ["kokoro-zh", "de_DE-thorsten-high"]}},
                                        warn=warned.append)
        self.assertEqual(cfg.packs, ["kokoro-zh", "de_DE-thorsten-high"])
        self.assertFalse(warned)

    def test_variant_follows_read_aloud_kokoro_then_what_is_there(self):
        self.assertEqual(speak.zh_variant("int8", ["fp32", "int8"]), "int8")
        self.assertEqual(speak.zh_variant("fp32", ["int8"]), "int8")
        self.assertEqual(speak.zh_variant("fp32", []), "")


class Language(unittest.TestCase):
    def test_chinese_with_english_words_is_chinese(self):
        self.assertEqual(speak.detect_languages("我用Python写代码。"), ["zh", "ja"])
        self.assertEqual(speak.detect_languages("今天我们用ChatGPT和Claude写了一个小工具，效果很好。"), ["zh", "ja"])
        self.assertEqual(speak.detect_languages("日本語のテキストです"), ["ja"])
        self.assertEqual(speak.detect_languages("This is plain English text with one word 中文 in it, see."), ["en"])

    def test_auto_language_picks_the_mandarin_voice(self):
        voices = speak.kokoro_voices() + speak.zh_voices() + [HUIHUI]
        cfg = speak.Config(voice="af_heart")
        v, note = speak.pick_voice(cfg, "春天来了，河边的柳树长出了嫩绿的新芽。", voices)
        self.assertEqual(v.id, speak.DEFAULT_FOR_LANGUAGE["zh"])
        self.assertIn("Chinese", note)
        last = f"kokoro-zh:{list(speak.ZH_VOICES)[-1]}"
        cfg = speak.Config(voice="af_heart", voices={"zh": last})
        self.assertEqual(speak.pick_voice(cfg, "春天来了，河边的柳树长出了嫩绿的新芽。", voices)[0].id, last)
        # Without the Mandarin voices a Windows one reads it; with neither, the note says where to get one.
        self.assertEqual(speak.pick_voice(speak.Config(), "春天来了，河边的柳树长出了嫩绿的新芽。",
                                          [*speak.kokoro_voices(), HUIHUI])[0], HUIHUI)
        v, note = speak.pick_voice(speak.Config(), "春天来了，河边的柳树长出了嫩绿的新芽。", speak.kokoro_voices())
        self.assertEqual(v.id, "af_heart")
        self.assertIn("Download one under Read aloud", note)

    def test_a_chosen_mandarin_voice_that_is_gone_falls_back_within_its_language(self):
        cfg = speak.Config(voice=speak.DEFAULT_FOR_LANGUAGE["zh"], auto_language=False)
        v, note = speak.pick_voice(cfg, "你好", [*speak.kokoro_voices(), HUIHUI])
        self.assertEqual(v, HUIHUI)
        self.assertIn("is not available", note)


class Pieces(unittest.TestCase):
    def test_spoken_length_counts_a_character_as_three_letters(self):
        self.assertEqual(speak.spoken_len("你好"), 6)
        self.assertEqual(speak.spoken_len("ab 你"), 6)

    def test_long_chinese_sentences_split_at_their_commas(self):
        clause = "这家银行的行长说明年的利率可能会小幅上调"   # 19 characters, 57 letters' worth
        sentence = "，".join([clause] * 6) + "。"
        pieces = speak.pieces(sentence)
        self.assertGreater(len(pieces), 1)
        self.assertTrue(all(speak.spoken_len(p.text) <= speak.FIRST_CHARS for p in pieces[:1]))
        self.assertTrue(all(speak.spoken_len(p.text) <= speak.HARD_CHARS for p in pieces))
        self.assertTrue(all(p.text.endswith(("，", "。")) for p in pieces))
        self.assertEqual("".join(p.text for p in pieces), sentence)   # no spaces added, nothing lost
        self.assertEqual([p.end for p in pieces][-1], "paragraph")

    def test_a_clause_without_punctuation_is_cut_within_the_limit(self):
        text = "长" * 200
        parts = speak._split_long(text, speak.HARD_CHARS)
        self.assertEqual("".join(parts), text)
        self.assertTrue(all(speak.spoken_len(p) <= speak.HARD_CHARS for p in parts))

    def test_latin_text_still_splits_as_before(self):
        long = ("This sentence goes on, and on, and on for a while, until it is longer than the first piece may "
                "be, which is the point of this test, and it ends here.")
        pieces = speak.pieces(long)
        self.assertEqual(pieces[0].text, "This sentence goes on, and on, and on for a while, until it is longer than "
                                         "the first piece may be,")
        self.assertEqual(" ".join(p.text for p in pieces), long)

    def test_chinese_lines_keep_their_own_punctuation(self):
        self.assertEqual(speak.speech_text("第一点：\n第二点，\n第三点"), "第一点：\n第二点，\n第三点.")

    def test_full_width_digits_and_letters_for_misaki(self):
        self.assertEqual(speak.for_zh("２０２６年，ＡＩ　助手占５０％。"), "2026年，AI 助手占50%。")


class Install(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.hf = self.tmp / "hf"
        self.profile = {"name": "TESTBOX", "data_dir": str(self.tmp / "data"),
                        "media": {"hf_home": str(self.hf)}, "read_aloud": {"kokoro": "fp32"},
                        "dictation": {"env_dir": str(self.tmp / "dictation")}}
        self.site = dictation._site_packages(self.profile)
        self.site.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_installed_needs_the_packages_and_a_full_set_of_files(self):
        with mock.patch.object(dictation, "installed", return_value=True):
            self.assertEqual(dictation.zh_variants(self.profile), [])
            snap = fake_zh_files(self.hf, voices=list(speak.ZH_VOICES)[:-1])   # one voice short: not a full set
            self.assertEqual(dictation.zh_variants(self.profile), [])
            (snap / speak.ZH_FILES["fp32"]).unlink()
            fake_zh_files(self.hf, variants=("int8",))                          # every voice, the int8 weights
            self.assertEqual(dictation.zh_variants(self.profile), ["int8"])
            self.assertFalse(dictation.zh_installed(self.profile))      # misaki missing
            fake_packages(self.site)
            self.assertTrue(dictation.zh_installed(self.profile))
            self.assertEqual(dictation.installed_packs(self.profile), ["kokoro-zh"])
            self.assertEqual(sorted(dictation.zh_package_names(self.profile)),
                             sorted(p.split("==")[0] for p in speak.ZH_PACKAGES
                                    if p.split("==")[0].replace("-", "_") in dictation.ZH_MODULES))

    def test_download_packs_hands_the_mandarin_set_to_install_zh(self):
        with mock.patch.object(dictation, "install_zh", return_value="Mandarin voices: done") as zh, \
                mock.patch.object(dictation, "download_piper") as piper:
            self.assertEqual(dictation.download_packs(self.profile, ["kokoro-zh"]), "Mandarin voices: done")
        zh.assert_called_once()
        piper.assert_not_called()   # no voices folder needed for it

    def test_install_zh_installs_pinned_packages_checks_them_then_downloads(self):
        fake_packages(self.site, ("espeakng_loader",))
        calls = []
        ok = mock.Mock(returncode=0, stdout="ok\n", stderr="")
        with mock.patch.object(dictation, "installed", return_value=True), \
                mock.patch.object(dictation, "_run", side_effect=lambda cmd, env=None: calls.append(
                    [str(c) for c in cmd])), \
                mock.patch("subprocess.run", return_value=ok) as check:
            note = dictation.install_zh(self.profile)
        self.assertEqual(calls[0][1:3], ["pip", "install"])
        self.assertEqual(calls[0][-len(speak.ZH_PACKAGES):], list(speak.ZH_PACKAGES))
        self.assertIn("regex._regex", check.call_args.args[0][-1])   # the compiled module must load
        self.assertEqual(calls[1][-3:], ["stacklib.dictation", "speak", "--download-zh"])
        self.assertIn("misaki installed", note)

    def test_install_zh_skips_what_is_there_and_reports_a_refused_dll(self):
        fake_packages(self.site, ("espeakng_loader", *dictation.ZH_MODULES))
        fake_zh_files(self.hf)
        refused = mock.Mock(returncode=1, stdout="", stderr="ImportError: DLL load failed while importing _regex: An "
                                                             "Application Control policy has blocked this file.")
        with mock.patch.object(dictation, "installed", return_value=True), \
                mock.patch.object(dictation, "_run") as run, mock.patch("subprocess.run", return_value=refused):
            with self.assertRaisesRegex(RuntimeError, "Smart App Control"):
                dictation.install_zh(self.profile)
        run.assert_not_called()
        with mock.patch.object(dictation, "installed", return_value=True), mock.patch.object(dictation, "_run") as run, \
                mock.patch("subprocess.run", return_value=mock.Mock(returncode=0, stdout="ok", stderr="")):
            note = dictation.install_zh(self.profile)
        run.assert_not_called()
        self.assertEqual(note, "Mandarin voices: misaki already installed; Mandarin voices already downloaded")

    def test_install_zh_needs_read_aloud(self):
        with mock.patch.object(dictation, "installed", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "read aloud is not installed"):
                dictation.install_zh(self.profile)

    def test_remove_takes_the_packages_then_the_folder_and_forgets_it(self):
        snap = fake_zh_files(self.hf)
        self.profile["read_aloud"]["packs"] = ["kokoro-zh", "de_DE-thorsten-high"]
        with mock.patch.object(install, "_set_packs") as set_packs, \
                mock.patch.object(uninstall, "_remove_zh_packages", return_value=1000) as pkgs:
            note = uninstall.remove_voice_pack(self.profile, "kokoro-zh")
        set_packs.assert_called_once_with(self.profile, ["de_DE-thorsten-high"])
        pkgs.assert_called_once()
        self.assertFalse(snap.parents[1].exists())
        self.assertIn("deleted the Mandarin voices", note)

    def test_remove_checks_the_folder_before_it_changes_anything(self):
        fake_zh_files(self.hf)
        odd = uninstall.Item("x", str(self.hf / "elsewhere"), 0.0, "hf")
        with mock.patch.object(install, "_set_packs"), mock.patch.object(uninstall, "_zh_item", return_value=odd), \
                mock.patch.object(uninstall, "_remove_zh_packages") as pkgs:
            with self.assertRaises(PermissionError):
                uninstall.remove_voice_pack(self.profile, "kokoro-zh")
        pkgs.assert_not_called()

    def test_package_removal_stops_and_restarts_voice_typing(self):
        fake_packages(self.site)
        status = [{"service": "dictation", "healthy": True}]
        with mock.patch.object(dictation, "installed", return_value=True), \
                mock.patch("stacklib.services.status", return_value=status), \
                mock.patch("stacklib.services.stop") as stop, mock.patch("stacklib.services.start") as start, \
                mock.patch.object(uninstall, "_run", return_value=mock.Mock(returncode=1, stderr="locked", stdout="")):
            with self.assertRaisesRegex(RuntimeError, "could not uninstall"):
                uninstall._remove_zh_packages(self.profile, lambda *a: None)
        stop.assert_called_once()
        start.assert_called_once()   # started again even though uv failed

    def test_removing_read_aloud_takes_the_mandarin_set(self):
        fake_zh_files(self.hf)
        fake_packages(self.site)
        status = {f.id: features.Status(True, True, "Installed") for f in features.FEATURES}
        with mock.patch.object(uninstall, "_kokoro_item", return_value=None):
            r = uninstall.plan(self.profile, "read_aloud", status)
        self.assertTrue(any(i.kind == "hf" and "Kokoro-82M-v1.1-zh" in i.path for i in r.deletes))
        self.assertTrue(any(i.kind == "packages" and "misaki" in i.what for i in r.deletes))

    def test_worker_plan(self):
        with mock.patch.object(install, "spawn_worker", return_value=3) as spawn:
            install.start_voice_packs(self.profile, remove=["kokoro-zh"])
        p = spawn.call_args.args[0]
        self.assertEqual((p.remove_voices, p.targets), (["kokoro-zh"], ["read_aloud"]))


class Counted(unittest.TestCase):
    def test_estimate_adds_disk_and_memory(self):
        hw = features.Hardware(vram_gb=12, desktop_vram_gb=1, ram_gb=32, threads=12)
        with mock.patch.object(features, "_kokoro_cached", return_value=True):
            base = features.estimate("read_aloud", {"read_aloud": {"kokoro": "fp32", "device": "cpu"}}, hw)
            more = features.estimate("read_aloud", {"read_aloud": {"kokoro": "fp32", "device": "cpu",
                                                                   "packs": ["kokoro-zh"]}}, hw)
            gpu = features.estimate("read_aloud", {"read_aloud": {"kokoro": "fp32", "device": "gpu",
                                                                  "packs": ["kokoro-zh"]}}, hw)
        self.assertAlmostEqual(more.disk_gb - base.disk_gb, speak.pack_disk_mb("kokoro-zh") / 1000)
        self.assertAlmostEqual(more.ram_gb - base.ram_gb, ZH["variants"]["fp32"]["ram_gb"])
        self.assertAlmostEqual(gpu.vram_gb, 1.0 + ZH["gpu_vram_gb"])
        self.assertIn("Mandarin", more.basis)

    def test_storage_names_its_folder(self):
        with tempfile.TemporaryDirectory() as t:
            snap = fake_zh_files(Path(t))
            (snap / "tokenizer.json").write_bytes(b"x" * storage.MIN_BYTES)   # big enough to be listed
            out: list = []
            storage._hf_models({"media": {"hf_home": t}}, out, {})
        self.assertEqual([(e.name, e.level) for e in out], [("Kokoro-82M v1.1-zh", "ok")])

    def test_gpu_card_lists_it(self):
        health = {"read_aloud": {"engine": "unloaded", "unload_after_min": 30,
                                 "zh": {"engine": "ready", "device": "cuda", "model": "kokoro-82m-v1.1-zh fp32",
                                        "idle_s": 120}}}
        rows = gpu_models.rows([], health)
        self.assertEqual([(r["name"], r["by"], r["gpu"], r["unloads"]) for r in rows],
                         [("kokoro-82m-v1.1-zh fp32", "Read aloud", "100%", "in 28 min")])
        self.assertAlmostEqual(rows[0]["bytes"] / gpu_models.GIB, ZH["gpu_vram_gb"], places=2)

    def test_settings_picker_offers_the_voices_once_downloaded(self):
        with mock.patch.object(dictation, "zh_installed", return_value=True):
            settings.refresh_voice_choices({"read_aloud": {}})
        voice = next(s for s in settings.SETTINGS if (s.section, s.key) == ("read_aloud", "voice"))
        self.assertIn(speak.DEFAULT_FOR_LANGUAGE["zh"], voice.choices)
        self.assertEqual(voice.labels[speak.DEFAULT_FOR_LANGUAGE["zh"]], speak.zh_voices()[0].label)

    def test_status_lists_chinese(self):
        with mock.patch.object(dictation, "installed_packs", return_value=["kokoro-zh"]), \
                mock.patch.object(dictation, "read_aloud_installed", return_value=True):
            s = features._status_read_aloud({"read_aloud": {"enabled": True}})
        self.assertIn("More voices: Chinese, Mandarin.", s.detail)


@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("misaki"),
                     "the engine needs numpy and misaki (voice typing's environment)")
class Engine(unittest.TestCase):
    def setUp(self):
        from stacklib.dictation import tts

        self.tts = tts

    def test_misaki_gives_kokoro_v11_zh_phonemes(self):
        g2p = self.tts.zh_g2p(lambda en: f"<{en}>")
        self.assertEqual(g2p("你好，世界！")[0], "ㄋㄧ2ㄏㄠ3, ㄕ十4ㄐㄝ4!")
        self.assertIn("<Python>", g2p("我用Python写代码。")[0])
        self.assertIn("ㄦ4ㄌ应2ㄦ4", g2p(speak.for_zh("２０２６年"))[0])   # numbers read out in Chinese

    def test_speech_routes_mandarin_voices_to_their_model(self):
        speech = self.tts.Speech(lambda *_: None)
        voice = speak.zh_voices()[0]
        cfg = speak.Config(enabled=True, kokoro="int8", device="cpu")
        with mock.patch.object(self.tts, "zh_cached", side_effect=lambda v: v == "fp32"), \
                mock.patch.object(speech, "kokoro_installed", return_value=True), \
                mock.patch.object(speech, "_has", return_value=True), \
                mock.patch.object(speech.kokoro_zh, "synth",
                                  return_value=self.tts.Audio(b"\x00\x00" * 2400, 0.1)) as synth:
            self.assertIn(voice, speech.voices(cfg))
            self.assertEqual(speech.zh_variant(cfg), "fp32")   # int8 asked for, only fp32 downloaded
            speech.synth("你好。", voice, 1.0, cfg)
        self.assertEqual(synth.call_args.args[3], "fp32")
        self.assertEqual(speech.workers(voice), 2)   # on the CPU, like Kokoro
        self.assertEqual(speech.model_name(voice, cfg), "kokoro-82m-v1.1-zh")
        with self.assertRaises(self.tts.SpeechError):
            speech.synth("你好。", voice, 1.0, speak.Config(enabled=True, kokoro="off"))

    def test_a_failed_misaki_fails_the_load(self):
        zh = self.tts.KokoroZh(lambda *_: None)
        with mock.patch.object(self.tts, "zh_g2p", side_effect=ImportError("no module named misaki")):
            zh._prepare()
            with self.assertRaisesRegex(self.tts.SpeechError, "misaki did not load"):
                zh._prepared()


if __name__ == "__main__":
    unittest.main()
