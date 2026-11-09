"""Read aloud's Thai voices: Kokoro Thai (kunato/wayu-kokoro-thai-v1) from config/installer.yaml kokoro_th
(stacklib/dictation/speak.py, tts.py and thai/), installed and removed through the setup worker like the Mandarin voices
(dictation, install.py, uninstall.py), counted by the features estimate, the Storage card and the GPU card. Nothing
here downloads, installs or deletes anything outside a temporary folder, and nothing loads a model.

The Engine class at the end needs numpy, pythainlp and tltk (voice typing's environment once the Thai voices are
downloaded); run it there by hand:
    C:/media/dictation/.venv/Scripts/python.exe -m unittest test_kokoro_th   (with PYTHONPATH=scripts;tests)

Checked by hand on 2026-11-08 (memory/state.md): the 12 voices through Whisper large-v3-turbo, speed and memory on
the CPU and the RTX 3060, and tltk loaded without its heavy dependencies against the full install on 4,004 inputs.
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

TH = catalog.section("kokoro_th")
PATTARA = speak.Voice("windows:Microsoft Pattara", "Pattara", "th-th", "windows", "male", "HKEY_LOCAL_MACHINE\\t")


def fake_th_files(hf: Path, skip: tuple[str, ...] = ()) -> Path:
    """The Thai model's snapshot folder in a fake Hugging Face cache, with tiny stand-ins for its files."""
    snap = hf / "hub" / f"models--{speak.TH_REPO.replace('/', '--')}" / "snapshots" / speak.TH_REVISION
    for name in speak.th_files("fp32"):
        if name in skip:
            continue
        (snap / name).parent.mkdir(parents=True, exist_ok=True)
        (snap / name).write_bytes(b"x" * 1000)
    return snap


def fake_packages(site: Path, modules=dictation.TH_MODULES) -> None:
    for m in modules:
        (site / m).mkdir(parents=True, exist_ok=True)
        (site / m / "__init__.py").write_text("", encoding="utf-8")


class Catalog(unittest.TestCase):
    def test_pinned_and_every_file_checked(self):
        self.assertEqual(TH["repo"], "kunato/wayu-kokoro-thai-v1")
        self.assertRegex(TH["revision"], r"^[0-9a-f]{40}$")
        self.assertEqual(TH["licence"], "Apache-2.0")
        self.assertIn("CC-BY-NC", TH["data_licence"])   # the teacher's licence is said, not hidden
        self.assertEqual(list(speak.TH.weights), ["fp32"])
        self.assertEqual(len(speak.TH.weights["fp32"]), 3)
        for name in speak.th_files("fp32"):
            with self.subTest(file=name):
                self.assertRegex(speak.TH.sha256[name], r"^[0-9a-f]{64}$")
        self.assertTrue(all(p.count("==") == 1 for p in speak.TH.packages))   # every package pinned
        self.assertTrue(speak.TH.no_deps)                                     # tltk's scikit-learn 1.2 never comes
        self.assertEqual({p.split("==")[0] for p in speak.TH.packages}, {"pythainlp", "tltk", "tzdata"})
        self.assertEqual(set(dictation.TH_MODULES), {p.split("==")[0] for p in speak.TH.packages})

    def test_twelve_speakers_each_once(self):
        self.assertEqual(len(speak.TH.voices), 12)
        self.assertEqual(sorted(speak.TH_SPEAKERS.values()), list(range(12)))
        for vid, (gender, name, _n) in speak.TH.voices.items():
            with self.subTest(voice=vid):
                self.assertEqual(gender, {"f": "female", "m": "male"}[vid[0]])
                self.assertTrue(name)
        self.assertEqual(next(iter(speak.TH.voices)), "f_young_clear")   # the default for Thai text


class Voices(unittest.TestCase):
    def test_ids_names_and_labels(self):
        v = speak.th_voice("kokoro-th:f_young_clear")
        self.assertEqual((v.engine, v.language, v.family), ("kokoro-th", "th-th", "th"))
        self.assertEqual(v.label, "Young, clear (Thai, female)")
        self.assertIsNone(speak.th_voice("kokoro-th:f_nobody"))
        self.assertIsNone(speak.th_voice("f_young_clear"))           # the prefix names the model
        self.assertIsNone(speak.zh_voice("kokoro-th:f_young_clear"))
        self.assertEqual(speak.known_voice("kokoro-th:m_mid_warm").name, "Middle-aged, warm")
        self.assertTrue(speak.kokoro_engine("kokoro-th"))
        self.assertEqual(speak.DEFAULT_FOR_LANGUAGE["th"], "kokoro-th:f_young_clear")

    def test_choices_list_them_only_when_downloaded(self):
        ids = [vid for vid, _ in speak.voice_choices([], packs_dir="")]
        self.assertFalse(any(i.startswith("kokoro-th:") for i in ids))
        ids = [vid for vid, _ in speak.voice_choices([], packs_dir="", th=True)]
        self.assertEqual(sum(i.startswith("kokoro-th:") for i in ids), 12)

    def test_a_voice_set_beside_the_others(self):
        self.assertEqual(speak.pack_language("kokoro-th"), "th-th")
        self.assertEqual(speak.pack_title("kokoro-th"), "Thai: 12 Kokoro voices")
        for variant in ("fp32", "int8", "off"):   # one variant, whatever read_aloud.kokoro says
            self.assertEqual(speak.pack_size_mb("kokoro-th", variant), TH["variants"]["fp32"]["download_mb"])
        self.assertEqual(speak.pack_disk_mb("kokoro-th"), speak.pack_size_mb("kokoro-th") + TH["packages_mb"])
        self.assertIn("CC-BY-NC", speak.pack_note("kokoro-th"))
        self.assertEqual(speak.TH.variant("int8"), "fp32")
        self.assertEqual(speak.model_variant("kokoro-th", "int8", ["fp32"]), "fp32")

    def test_settings_accept_it(self):
        warned = []
        cfg = speak.Config.from_profile({"read_aloud": {"packs": ["kokoro-th", "kokoro-zh"]}}, warn=warned.append)
        self.assertEqual(cfg.packs, ["kokoro-th", "kokoro-zh"])
        self.assertFalse(warned)

    def test_auto_language_picks_the_thai_voice(self):
        voices = speak.kokoro_voices() + speak.th_voices() + [PATTARA]
        cfg = speak.Config(voice="af_heart", auto_language=True)
        voice, note = speak.pick_voice(cfg, "สวัสดีครับ วันนี้อากาศดีมาก เราไปเที่ยวทะเลกันไหม", voices)
        self.assertEqual(voice.id, "kokoro-th:f_young_clear")   # the Kokoro voice before the Windows one
        self.assertIn("Thai", note)
        cfg.voices = {"th": "kokoro-th:m_mid_warm"}
        self.assertEqual(speak.pick_voice(cfg, "สวัสดีครับ วันนี้อากาศดีมาก", voices)[0].id, "kokoro-th:m_mid_warm")

    def test_without_the_set_thai_text_says_where_to_get_it(self):
        _voice, note = speak.pick_voice(speak.Config(voice="af_heart"), "สวัสดีครับ วันนี้อากาศดีมาก",
                                        speak.kokoro_voices())
        self.assertIn("Features card", note)

    def test_thai_text_without_punctuation_is_cut_at_spaces(self):
        text = " ".join(["วันนี้อากาศดีมาก เราไปเที่ยวทะเลกันไหม"] * 12)
        parts = speak.pieces(speak.speech_text(text))
        self.assertGreater(len(parts), 1)
        self.assertLessEqual(len(parts[0].text), speak.FIRST_CHARS)
        self.assertTrue(all(len(p.text) <= speak.HARD_CHARS + 1 for p in parts))
        self.assertEqual("".join(p.text for p in parts).replace(" ", ""),
                         speak.speech_text(text).replace(" ", ""))   # nothing lost or added but the end mark


class Install(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.hf = self.tmp / "hf"
        self.profile = {"name": "TESTBOX", "data_dir": str(self.tmp / "data"),
                        "media": {"hf_home": str(self.hf)}, "read_aloud": {"kokoro": "int8"},
                        "dictation": {"env_dir": str(self.tmp / "dictation")}}
        self.site = dictation._site_packages(self.profile)
        self.site.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_installed_needs_the_packages_and_every_file(self):
        with mock.patch.object(dictation, "installed", return_value=True):
            self.assertEqual(dictation.th_variants(self.profile), [])
            snap = fake_th_files(self.hf, skip=("onnx/styles.npz",))
            self.assertEqual(dictation.th_variants(self.profile), [])   # the voices' styles missing
            (snap / "onnx" / "styles.npz").write_bytes(b"x")
            self.assertEqual(dictation.th_variants(self.profile), ["fp32"])
            self.assertFalse(dictation.th_installed(self.profile))      # pythainlp and tltk missing
            fake_packages(self.site)
            self.assertTrue(dictation.th_installed(self.profile))
            self.assertEqual(dictation.installed_packs(self.profile), ["kokoro-th"])
            self.assertEqual(sorted(dictation.th_package_names(self.profile)), ["pythainlp", "tltk", "tzdata"])

    def test_a_package_another_installed_set_needs_stays(self):
        fake_packages(self.site)
        fake_packages(self.site, dictation.ZH_MODULES)
        with mock.patch.dict(speak.MODEL_PACKS, {"kokoro-zh": speak.ZH.__class__(
                **{**speak.ZH.__dict__, "packages": (*speak.ZH.packages, "tzdata==2026.6")})}):
            self.assertNotIn("tzdata", dictation.th_package_names(self.profile))

    def test_download_packs_hands_the_thai_set_to_install_th(self):
        with mock.patch.object(dictation, "install_th", return_value="Thai voices: done") as th, \
                mock.patch.object(dictation, "install_zh") as zh, \
                mock.patch.object(dictation, "download_piper") as piper:
            self.assertEqual(dictation.download_packs(self.profile, ["kokoro-th"]), "Thai voices: done")
        th.assert_called_once()
        zh.assert_not_called()
        piper.assert_not_called()

    def test_install_th_installs_without_dependencies_checks_then_downloads(self):
        fake_packages(self.site, ("espeakng_loader",))
        calls = []
        ok = mock.Mock(returncode=0, stdout="ok\n", stderr="")
        with mock.patch.object(dictation, "installed", return_value=True), \
                mock.patch.object(dictation, "_run", side_effect=lambda cmd, env=None: calls.append(
                    [str(c) for c in cmd])), \
                mock.patch("subprocess.run", return_value=ok) as check:
            note = dictation.install_th(self.profile)
        self.assertEqual(calls[0][1:3], ["pip", "install"])
        self.assertEqual(calls[0][-len(speak.TH.packages) - 1:], ["--no-deps", *speak.TH.packages])
        self.assertIn("load_tltk", open(REPO / "scripts/stacklib/dictation/thai/g2p.py", encoding="utf-8").read())
        self.assertIn("ThaiG2P", check.call_args.args[0][-1])   # the front-end itself must load
        self.assertEqual(calls[1][-3:], ["stacklib.dictation", "speak", "--download-th"])
        self.assertEqual(note, "Thai voices: pythainlp and tltk installed; Thai voices downloaded")

    def test_install_th_skips_what_is_there_and_reports_a_failed_load(self):
        fake_packages(self.site, ("espeakng_loader", *dictation.TH_MODULES))
        fake_th_files(self.hf)
        broken = mock.Mock(returncode=1, stdout="", stderr="ModuleNotFoundError: No module named 'pythainlp.util'")
        with mock.patch.object(dictation, "installed", return_value=True), \
                mock.patch.object(dictation, "_run") as run, mock.patch("subprocess.run", return_value=broken):
            with self.assertRaisesRegex(RuntimeError, "pythainlp and tltk's packages do not load"):
                dictation.install_th(self.profile)
        run.assert_not_called()
        with mock.patch.object(dictation, "installed", return_value=True),                 mock.patch.object(dictation, "_run") as run, \
                mock.patch("subprocess.run", return_value=mock.Mock(returncode=0, stdout="ok", stderr="")):
            note = dictation.install_th(self.profile)
        run.assert_not_called()   # int8 asked for: the Thai set's fp32 is what it has, and it is there
        self.assertEqual(note, "Thai voices: pythainlp and tltk already installed; Thai voices already downloaded")

    def test_install_th_needs_read_aloud(self):
        with mock.patch.object(dictation, "installed", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "read aloud is not installed"):
                dictation.install_th(self.profile)

    def test_remove_takes_the_packages_then_the_folder_and_forgets_it(self):
        snap = fake_th_files(self.hf)
        self.profile["read_aloud"]["packs"] = ["kokoro-th", "kokoro-zh"]
        with mock.patch.object(install, "_set_packs") as set_packs, \
                mock.patch.object(uninstall, "_remove_th_packages", return_value=1000) as pkgs, \
                mock.patch.object(uninstall, "_remove_zh_packages") as zh:
            note = uninstall.remove_voice_pack(self.profile, "kokoro-th")
        set_packs.assert_called_once_with(self.profile, ["kokoro-zh"])
        pkgs.assert_called_once()
        zh.assert_not_called()
        self.assertFalse(snap.parents[1].exists())
        self.assertIn("deleted the Thai voices", note)

    def test_remove_checks_the_folder_before_it_changes_anything(self):
        fake_th_files(self.hf)
        odd = uninstall.Item("x", str(self.hf / "elsewhere"), 0.0, "hf")
        with mock.patch.object(install, "_set_packs"), mock.patch.object(uninstall, "_th_item", return_value=odd), \
                mock.patch.object(uninstall, "_remove_th_packages") as pkgs:
            with self.assertRaises(PermissionError):
                uninstall.remove_voice_pack(self.profile, "kokoro-th")
        pkgs.assert_not_called()

    def test_package_removal_stops_and_restarts_voice_typing(self):
        fake_packages(self.site)
        status = [{"service": "dictation", "healthy": True}]
        with mock.patch.object(dictation, "installed", return_value=True), \
                mock.patch("stacklib.services.status", return_value=status), \
                mock.patch("stacklib.services.stop") as stop, mock.patch("stacklib.services.start") as start, \
                mock.patch.object(uninstall, "_run", return_value=mock.Mock(returncode=0, stderr="", stdout="")) as run:
            uninstall._remove_th_packages(self.profile, lambda *a: None)
        self.assertEqual(run.call_args.args[0][-3:], ["pythainlp", "tltk", "tzdata"])
        stop.assert_called_once()
        start.assert_called_once()

    def test_removing_read_aloud_takes_the_thai_set_too(self):
        fake_th_files(self.hf)
        fake_packages(self.site)
        status = {f.id: features.Status(True, True, "Installed") for f in features.FEATURES}
        with mock.patch.object(uninstall, "_kokoro_item", return_value=None):
            r = uninstall.plan(self.profile, "read_aloud", status)
        self.assertTrue(any(i.kind == "hf" and "wayu-kokoro-thai-v1" in i.path for i in r.deletes))
        self.assertTrue(any(i.kind == "packages" and "tltk" in i.what for i in r.deletes))

    def test_plan_lists_kokoro_sets_without_a_piper_folder(self):
        """installed_packs names the Kokoro sets too; the Piper rows of a removal plan must skip them."""
        with mock.patch.object(dictation, "installed_packs", return_value=["kokoro-zh", "kokoro-th"]):
            self.assertEqual(uninstall._pack_items(self.profile), [])

    def test_worker_plan(self):
        with mock.patch.object(install, "spawn_worker", return_value=3) as spawn:
            install.start_voice_packs(self.profile, download=["kokoro-th"])
        p = spawn.call_args.args[0]
        self.assertEqual(p.targets, ["read_aloud"])


class Counted(unittest.TestCase):
    def test_estimate_adds_disk_and_memory(self):
        hw = features.Hardware(vram_gb=12, desktop_vram_gb=1, ram_gb=32, threads=12)
        with mock.patch.object(features, "_kokoro_cached", return_value=True):
            base = features.estimate("read_aloud", {"read_aloud": {"kokoro": "fp32", "device": "cpu"}}, hw)
            more = features.estimate("read_aloud", {"read_aloud": {"kokoro": "fp32", "device": "cpu",
                                                                   "packs": ["kokoro-th"]}}, hw)
            gpu = features.estimate("read_aloud", {"read_aloud": {"kokoro": "fp32", "device": "gpu",
                                                                  "packs": ["kokoro-th"]}}, hw)
        self.assertAlmostEqual(more.disk_gb - base.disk_gb, speak.pack_disk_mb("kokoro-th") / 1000)
        self.assertAlmostEqual(more.ram_gb - base.ram_gb, TH["variants"]["fp32"]["ram_gb"])
        self.assertAlmostEqual(gpu.vram_gb, 1.0 + TH["gpu_vram_gb"])
        self.assertIn("Thai", more.basis)

    def test_storage_names_its_folder(self):
        with tempfile.TemporaryDirectory() as t:
            snap = fake_th_files(Path(t))
            (snap / "onnx" / "decoder_fp32.onnx").write_bytes(b"x" * storage.MIN_BYTES)   # big enough to be listed
            out: list = []
            storage._hf_models({"media": {"hf_home": t}}, out, {})
        self.assertEqual([(e.name, e.level) for e in out], [("Kokoro Thai", "ok")])

    def test_gpu_card_lists_it(self):
        health = {"read_aloud": {"engine": "unloaded", "unload_after_min": 30,
                                 "th": {"engine": "ready", "device": "cuda", "model": "wayu-kokoro-thai-v1 fp32",
                                        "idle_s": 60}}}
        rows = gpu_models.rows([], health)
        self.assertEqual([(r["name"], r["by"], r["gpu"], r["unloads"]) for r in rows],
                         [("wayu-kokoro-thai-v1 fp32", "Read aloud", "100%", "in 29 min")])
        self.assertAlmostEqual(rows[0]["bytes"] / gpu_models.GIB, TH["gpu_vram_gb"], places=2)

    def test_settings_picker_offers_the_voices_once_downloaded(self):
        with mock.patch.object(dictation, "th_installed", return_value=True), \
                mock.patch.object(dictation, "zh_installed", return_value=False):
            settings.refresh_voice_choices({"read_aloud": {}})
        voice = next(s for s in settings.SETTINGS if (s.section, s.key) == ("read_aloud", "voice"))
        self.assertIn("kokoro-th:f_young_clear", voice.choices)
        self.assertEqual(voice.labels["kokoro-th:f_young_clear"], "Young, clear (Thai, female)")
        self.assertFalse(any(c.startswith("kokoro-zh:") for c in voice.choices))

    def test_status_lists_thai(self):
        with mock.patch.object(dictation, "installed_packs", return_value=["kokoro-th"]), \
                mock.patch.object(dictation, "read_aloud_installed", return_value=True):
            s = features._status_read_aloud({"read_aloud": {"enabled": True}})
        self.assertIn("More voices: Thai.", s.detail)


class FrontEnd(unittest.TestCase):
    """The Thai front-end's own steps, with a stand-in for tltk (no pythainlp or tltk needed)."""

    def setUp(self):
        from stacklib.dictation.thai import g2p

        self.g2p = g2p
        self.front = g2p.ThaiG2P.__new__(g2p.ThaiG2P)   # skip __init__: it imports pythainlp
        self.front.vocab = frozenset("abcdefghijklmnopqrstuwxyzŋɔɛɤɯʔʰːˈ ,.!?") | set(g2p.TONE_DIGIT_TO_TOKEN.values())
        self.front.english = lambda s: f"ˈ{s.lower()}"
        self.front.normalize_text = lambda s: s

        class FakeTltk:
            def th2ipa(self, text):
                return {"สวัสดี": "sa2.wat2.diː1<s/>", "ครับ": "kʰrap4<s/>", "ทะเล": "tʰa4.leː1<s/>"}.get(text, "")

        self.front.tltk = FakeTltk()

    def test_tone_digits_become_kokoro_tone_tokens(self):
        self.assertEqual(self.front.thai_tokens("สวัสดี").strip(), "sa˩wat˩diː→")   # render strips the word break
        self.assertEqual(self.front.thai_tokens("ครับ").strip(), "kʰrap↗")
        self.assertEqual(self.g2p.TONE_DIGIT_TO_TOKEN, {"1": "→", "2": "˩", "3": "↘", "4": "↗", "5": "↓"})

    def test_english_inside_thai_goes_to_the_english_callable(self):
        self.assertEqual(self.front.render("สวัสดี Google ครับ"), "sa˩wat˩diː→ ˈgoogle kʰrap↗")

    def test_characters_outside_the_vocabulary_are_dropped(self):
        self.front.tltk.th2ipa = lambda text: "ka1-ka1 ᴐ1"   # tltk's reduplication dash; its own ɔ
        self.assertEqual(self.front.thai_tokens("กาๆ"), "ka→ka→ ɔ→")

    def test_a_word_tltk_fails_on_is_read_syllable_by_syllable(self):
        def th2ipa(text):
            if text == "ทะเลสวัสดี":
                raise ValueError("tltk could not segment it")
            return {"ทะ": "tʰa4", "เล": "leː1", "สวัส": "sa2.wat2", "ดี": "diː1"}.get(text, "")

        self.front.tltk.th2ipa = th2ipa
        with mock.patch.object(self.g2p, "_syllables", return_value=["ทะ", "เล", "สวัส", "ดี"]):
            self.assertEqual(self.front.thai_tokens("ทะเลสวัสดี"), "tʰa↗ leː→ sa˩wat˩ diː→")

    def test_loanword_overrides_skip_tltk(self):
        self.front.tltk.th2ipa = lambda text: ""
        self.assertEqual(self.front.thai_tokens("ทรู").strip(), "tʰruː→")


@unittest.skipUnless(importlib.util.find_spec("numpy"), "the model's host-side steps need numpy")
class Model(unittest.TestCase):
    def test_harmonic_source_shape_and_determinism(self):
        import numpy as np

        from stacklib.dictation.thai import model

        g = model.Graphs(None, None, None, source_weight=np.full((1, 9), 0.1), source_bias=np.zeros(1),
                         window=np.hanning(model.N_FFT))
        f0 = np.full((1, 40), 120.0)
        a, b = model.harmonic_source(g, f0, 7), model.harmonic_source(g, f0, 7)
        frames = (40 * model.UPSAMPLE_SCALE) // model.HOP + 1
        self.assertEqual(a.shape, (1, model.N_FFT + 2, frames))   # magnitude and phase of 11 bins
        self.assertTrue(np.array_equal(a, b))                      # the same seed, the same sound

    def test_providers_are_those_all_three_graphs_use(self):
        from stacklib.dictation.thai import model

        s = lambda *p: mock.Mock(get_providers=lambda: list(p))  # noqa: E731
        g = model.Graphs(s("CUDAExecutionProvider", "CPUExecutionProvider"), s("CPUExecutionProvider"),
                         s("CUDAExecutionProvider", "CPUExecutionProvider"), None, None, None)
        self.assertEqual(g.get_providers(), ["CPUExecutionProvider"])


@unittest.skipUnless(all(importlib.util.find_spec(m) for m in ("numpy", "pythainlp", "tltk")),
                     "the engine needs numpy, pythainlp and tltk (voice typing's environment)")
class Engine(unittest.TestCase):
    def setUp(self):
        from stacklib.dictation import tts

        self.tts = tts

    def test_tltk_loads_without_its_heavy_dependencies(self):
        from stacklib.dictation.thai.g2p import load_tltk

        nlp = load_tltk()
        self.assertEqual(nlp.th2ipa("ครับ").replace("<s/>", "").strip(), "kʰrap4")
        self.assertNotIn("sklearn", sys.modules)   # the stand-ins are gone again
        self.assertNotIn("pandas", sys.modules)

    def test_tltk_gets_a_regex_cache_that_keeps_every_pattern(self):
        from stacklib.dictation.thai.g2p import load_tltk

        nlp = load_tltk()
        self.assertIsNot(nlp.re, __import__("re"))
        self.assertEqual(nlp.re.sub("a+", "b", "caat"), "cbt")
        self.assertEqual(nlp.re.match("(c)(a)", "cat").groups(), ("c", "a"))
        self.assertEqual(nlp.re.split(",", "a,b", 1), ["a", "b"])
        self.assertIs(nlp.re.compile("x+"), nlp.re.compile("x+"))   # compiled once

    def test_front_end_reads_numbers_and_tones(self):
        from stacklib.dictation.thai.g2p import TONE_DIGIT_TO_TOKEN, ThaiG2P

        vocab = set("abcdefhijklmnopqrstuvwxyzŋɔɛɤɯʔʰːɕʨ ,.!?") | set(TONE_DIGIT_TO_TOKEN.values())
        g = ThaiG2P(vocab, lambda s: "")
        self.assertEqual(g("สวัสดีครับ"), "sa˩wat˩diː→kʰrap↗")
        self.assertIn("sɔːŋ↓", g("2 คน"))   # the number written out in Thai first (สอง)

    def test_speech_routes_thai_voices_to_their_model(self):
        speech = self.tts.Speech(lambda *_: None)
        voice = speak.th_voices()[0]
        cfg = speak.Config(enabled=True, kokoro="int8", device="cpu")
        with mock.patch.object(self.tts, "th_cached", return_value=True), \
                mock.patch.object(speech, "kokoro_installed", return_value=True), \
                mock.patch.object(speech, "_has", return_value=True), \
                mock.patch.object(speech.kokoro_th, "synth",
                                  return_value=self.tts.Audio(b"\x00\x00" * 2400, 0.1)) as synth:
            self.assertIn(voice, speech.voices(cfg))
            self.assertEqual(speech.pack_variant("kokoro-th", cfg), "fp32")
            speech.synth("สวัสดีครับ", voice, 1.0, cfg)
        self.assertEqual(synth.call_args.args[3], "fp32")
        self.assertEqual(speech.workers(voice), 2)
        self.assertEqual(speech.model_name(voice, cfg), "wayu-kokoro-thai-v1")
        self.assertIn("th", speech.health())

    def test_a_failed_front_end_fails_the_load(self):
        th = self.tts.KokoroTh(lambda *_: None)
        with mock.patch.object(self.tts, "th_g2p", side_effect=ImportError("no module named pythainlp")):
            th._prepare()
            with self.assertRaisesRegex(self.tts.SpeechError, "pythainlp and tltk did not load"):
                th._prepared()


if __name__ == "__main__":
    unittest.main()
