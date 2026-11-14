"""The system check (stacklib/syscheck.py): what it reads from nvidia-smi and Windows, the recommendations it makes from
those facts, the report it keeps, and how setup's Check this PC step, the installer's first page and the tray use it.
Every report here is made up (no real PC's facts, languages or drives); the probes that read this PC are patched out.

Run with `uv run --with pytest python -m pytest -q tests/test_syscheck.py`.
"""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))
from stacklib import disks, features, install, syscheck  # noqa: E402
from test_features import make_profile  # noqa: E402

PARAKEET, CANARY, TURBO = "parakeet-tdt-0.6b-v3", "canary-qwen-2.5b", "large-v3-turbo"

SMI_OLD = "| NVIDIA-SMI 551.86     Driver Version: 551.86     CUDA Version: 12.4     |"
SMI_NEW = "| NVIDIA-SMI 610.88                 KMD Version: 610.88        CUDA UMD Version: 13.3     |"


def report(vram=12.0, desktop=1.0, vendor="NVIDIA", cuda="13.3", ram=32.0, avail=18.0, cores=6, avx2=True,
           langs=("en-US",), mics=1, speakers=1, sac=False, vulkan=True, drives=()) -> syscheck.Report:
    return syscheck.Report(
        checked_at=time.time(),
        gpu=syscheck.Gpu(vendor=vendor if vram else "", name="Test GPU" if vram else "", vram_gb=vram, used_gb=desktop,
                         driver="610.88", cuda=cuda if vendor == "NVIDIA" else "", compute="8.6", pcie_gen=3,
                         pcie_width=16, vulkan=vulkan),
        cpu=syscheck.Cpu(name="Test CPU", cores=cores, threads=cores * 2, avx2=avx2),
        memory=syscheck.Memory(total_gb=ram, available_gb=avail, speed_mts=3200, modules=2),
        system=syscheck.System(os="Windows test", smart_app_control=sac, long_paths=True, microphones=mics,
                               speakers=speakers, languages=list(langs), ollama="0.40.11", python_org=True, git=True,
                               winget=True, node="24.22.1"),
        drives=[asdict(d) for d in drives])


class Parse(unittest.TestCase):
    def test_cuda_from_both_banners(self):
        self.assertEqual(syscheck.parse_cuda(SMI_OLD), "12.4")
        self.assertEqual(syscheck.parse_cuda(SMI_NEW), "13.3")
        self.assertEqual(syscheck.parse_cuda("no banner"), "")

    def test_ram_modules(self):
        self.assertEqual(syscheck.parse_ram_modules("16 GB @ 2133 MT/s, 16 GB @ 2133 MT/s"), (2133, 2))
        self.assertEqual(syscheck.parse_ram_modules(""), (0, 0))

    def test_windows_language_tags(self):
        for tag, code in (("en-US", "en"), ("nb-NO", "no"), ("fil-PH", "tl"), ("zh-Hant-TW", "zh"), ("de", "de"),
                          ("x-klingon", "")):
            self.assertEqual(syscheck.whisper_code(tag), code, tag)

    def test_gpu_free_counts_the_stack_s_own_models_as_free(self):
        g = syscheck.Gpu(vendor="NVIDIA", vram_gb=12.0, used_gb=8.0, stack_gb=7.0)
        self.assertAlmostEqual((g.desktop_gb, g.free_gb), (1.0, 11.0))
        self.assertEqual(syscheck.Gpu(cuda="13.3").cuda_version, (13, 3))

    def test_an_unknown_field_does_not_lose_the_card(self):
        def run(cmd, timeout=15):
            q = next((c for c in cmd if c.startswith("--query-gpu=")), "")
            if q == "--query-gpu=name,memory.total,memory.used,driver_version":
                return "Old GPU, 8192, 500, 470.00\n"
            return "Field \"compute_cap\" is not a valid field to query.\n" if q else "no banner"
        with mock.patch.object(syscheck, "which", return_value="nvidia-smi"), mock.patch.object(syscheck, "_run", run):
            g = syscheck.probe_nvidia()
        self.assertEqual((g.name, g.vram_gb, g.compute, g.cuda), ("Old GPU", 8.0, "", ""))
        self.assertFalse(g.cuda_known)

    def test_no_nvidia_smi(self):
        with mock.patch.object(syscheck, "which", return_value=None):
            self.assertIsNone(syscheck.probe_nvidia())

    def test_stack_gpu_memory_adds_each_model_s_share(self):
        rows = [{"bytes": 6 * 2 ** 30, "gpu": "100%"}, {"bytes": 2 * 2 ** 30, "gpu": "50%"}, {"bytes": 2 ** 30, "gpu": "CPU"}]
        with mock.patch("stacklib.gpu_models.rows", return_value=rows), \
                mock.patch("stacklib.ollama.ps", return_value=[]), \
                mock.patch("stacklib.gpu_models.comfy_stats", return_value=None), \
                mock.patch("stacklib.dictation.control.call", side_effect=OSError):
            self.assertAlmostEqual(syscheck.stack_gpu_gb(make_profile(Path("."))), 7.0)


class Recommend(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        for target, value in ((features, "app_model_store"), (install, "current_tool_dir")):
            p = mock.patch.object(target, value, return_value="")
            p.start()
            self.addCleanup(p.stop)

    def run_check(self, r, **profile_over) -> syscheck.Report:
        return syscheck.recommend(r, make_profile(self.tmp, **profile_over))

    def level(self, r, key, value=""):
        v = r.verdict(key, value)
        self.assertIsNotNone(v, (key, value))
        return v.level

    def test_a_12_gb_card_and_32_gb_of_ram(self):
        r = self.run_check(report(sac=True))
        self.assertEqual(r.recommended("models.primary"), "qwen3.5:9b")
        self.assertEqual(self.level(r, "models.primary", "qwen3.6:35b-a3b-coding"), "ok")   # experts in RAM
        self.assertEqual(r.recommended("models.primary_num_ctx"), "32768")   # the largest measured one that fits
        self.assertEqual(self.level(r, "models.primary_num_ctx", "65536"), "ok")   # fits by the estimate only
        self.assertIn("estimated", r.verdict("models.primary_num_ctx", "65536").text)
        self.assertEqual(self.level(r, "tracing"), "not_recommended")        # Smart App Control
        self.assertEqual(self.level(r, "images"), "recommended")
        self.assertEqual(self.level(r, "voice_typing"), "ok")
        self.assertEqual(r.recommended("read_aloud.device"), "auto")
        self.assertTrue(any("Smart App Control" in n.text for n in r.notes))

    def test_english_only_with_room_on_the_gpu_takes_canary_qwen(self):
        r = self.run_check(report())
        self.assertEqual(r.recommended("dictation.model"), CANARY)
        self.assertEqual(self.level(r, "dictation.model", PARAKEET), "ok")
        self.assertIn("most accurate for English", r.verdict("dictation.model", CANARY).text)

    def test_a_language_parakeet_does_not_know_takes_whisper(self):
        r = self.run_check(report(langs=("en-US", "ja-JP")))
        self.assertEqual(r.recommended("dictation.model"), TURBO)
        for name in (PARAKEET, CANARY):
            v = r.verdict("dictation.model", name)
            self.assertEqual(v.level, "not_recommended")
            self.assertIn("Japanese", v.text)

    def test_european_languages_take_parakeet_off_the_gpu(self):
        r = self.run_check(report(langs=("de-DE", "en-GB")))
        self.assertEqual(r.recommended("dictation.model"), PARAKEET)
        self.assertEqual(self.level(r, "dictation.model", CANARY), "not_recommended")   # no German

    def test_vocabulary_hints_keep_whisper(self):
        r = self.run_check(report(), dictation={"model": TURBO, "vocabulary": "Logseq, LiteLLM"})
        self.assertEqual(r.recommended("dictation.model"), TURBO)
        self.assertIn("vocabulary hints", r.verdict("dictation.model", TURBO).text)

    def test_a_small_card(self):
        r = self.run_check(report(vram=6.0, desktop=0.5, langs=()))
        self.assertIsNone(r.recommended("models.primary"))   # the 9B does not fit 6 GB whole
        self.assertEqual(self.level(r, "models.primary", "qwen3.5:9b"), "not_recommended")
        self.assertEqual(self.level(r, "images"), "not_recommended")
        self.assertEqual(r.recommended("media.image_size"), "768x768")

    def test_no_gpu(self):
        r = self.run_check(report(vram=0.0, vendor="", vulkan=False, langs=()))
        self.assertEqual(self.level(r, "images"), "unavailable")
        self.assertEqual(r.recommended("dictation.model"), PARAKEET)   # quick on the CPU, any European language
        self.assertEqual(self.level(r, "dictation.model", CANARY), "not_recommended")
        self.assertIn("Whisper small instead", r.verdict("dictation.model", CANARY).text)
        self.assertEqual(r.recommended("read_aloud.device"), "cpu")
        self.assertEqual(self.level(r, "models.primary", "qwen3.6:35b-a3b-coding"), "not_recommended")
        self.assertEqual(r.verdicts.count(r.verdict("models.primary", "qwen3.5:9b")), 1)

    def test_an_unknown_cuda_version_is_not_an_old_one(self):
        r = self.run_check(report(cuda=""))
        self.assertEqual(self.level(r, "images"), "recommended")

    def test_whisper_small_stays_usable_on_a_slow_processor(self):
        r = self.run_check(report(vram=0.0, vendor="", vulkan=False, cores=4, langs=("en-US", "ja-JP")))
        self.assertEqual(r.recommended("dictation.model"), "small")
        self.assertEqual(self.level(r, "dictation.model", "base"), "ok")

    def test_the_owners_chat_model_sizes_the_rest(self):
        with mock.patch.object(install, "explicit_options", return_value={("models", "primary")}):
            r = self.run_check(report(), models={**make_profile(self.tmp)["models"], "primary": "qwen3.6:35b-a3b-coding"})
        ctx = r.verdict("models.primary_num_ctx", "32768")
        self.assertIn("qwen3.6:35b-a3b-coding", ctx.text)

    def test_an_old_driver(self):
        r = self.run_check(report(cuda="12.4"))
        self.assertEqual(self.level(r, "images"), "not_recommended")
        self.assertTrue(any("CUDA 13" in n.text and n.level == "warn" for n in r.notes))
        self.assertEqual(r.recommended("read_aloud.device"), "cpu")

    def test_no_microphone_or_speakers(self):
        r = self.run_check(report(mics=0, speakers=0))
        self.assertEqual(self.level(r, "voice_typing"), "not_recommended")
        self.assertEqual(self.level(r, "read_aloud"), "not_recommended")

    def test_an_amd_card_runs_canary_through_vulkan(self):
        r = self.run_check(report(vendor="AMD", vulkan=True))
        self.assertEqual(self.level(r, "images"), "unavailable")
        self.assertTrue(syscheck.speech_on_gpu(r, syscheck.SPEECH[CANARY]))
        self.assertFalse(syscheck.speech_on_gpu(r, syscheck.SPEECH[TURBO]))
        self.assertEqual(r.recommended("dictation.model"), CANARY)

    def test_a_moe_model_without_the_ram(self):
        r = self.run_check(report(ram=16.0, avail=8.0))
        v = r.verdict("models.primary", "qwen3.6:35b-a3b-coding")
        self.assertEqual(v.level, "not_recommended")
        self.assertIn("28 GB", v.text)

    def test_slow_models_drive_and_cold_load(self):
        d = disks.DriveSpeed(root=str(self.tmp)[:3], read_mbps=41.0, write_mbps=41.0, bus="USB", free_gb=800.0,
                             method="test file")
        with mock.patch.object(features, "effective_model_store", return_value=str(self.tmp)):
            r = self.run_check(report(drives=[d]))
        self.assertIn("cold load", r.verdict("models.primary", "qwen3.6:35b-a3b-coding").text)
        self.assertTrue(any("USB 2.0" in n.text for n in r.notes))

    def test_every_offered_feature_and_option_gets_a_verdict(self):
        r = self.run_check(report())
        for f in features.FEATURES:
            if f.offered:
                self.assertIsNotNone(r.verdict(f.id), f.id)
        for v in r.verdicts:
            self.assertIn(v.level, syscheck.LEVELS)
        keys = {v.key for v in r.verdicts}
        self.assertTrue({"models.primary", "models.primary_num_ctx", "dictation.model", "read_aloud.device"} <= keys)
        for key in ("models.primary", "models.primary_num_ctx", "dictation.model", "read_aloud.device",
                    "media.image_size"):
            self.assertLessEqual(sum(1 for v in r.verdicts if v.key == key and v.level == "recommended"), 1, key)


class Keep(unittest.TestCase):
    def test_saved_and_read_back(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "check.json"
            with mock.patch.object(features, "app_model_store", return_value=""):
                r = syscheck.recommend(report(), make_profile(Path(d)))
            syscheck.save(r, path)
            back = syscheck.load(path)
            self.assertEqual(back.verdicts, r.verdicts)
            self.assertEqual((back.gpu, back.cpu, back.system), (r.gpu, r.cpu, r.system))
            self.assertIsNone(syscheck.load(path, max_age_s=-1))
            self.assertIsNone(syscheck.load(Path(d) / "none.json"))
            hw = back.hardware()
            self.assertAlmostEqual((hw.vram_gb, hw.desktop_vram_gb), (12.0, 1.0))

    def test_broken_or_older_reports_read_as_none_or_skip_fields(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "check.json"
            for text in ("null", "[]", '"x"', '{"verdicts": ["a"]}', '{"gpu": [1]}', "{"):
                path.write_text(text, encoding="utf-8")
                self.assertIsNone(syscheck.load(path), text)
        r = report(drives=[disks.DriveSpeed(root="C:\\", read_mbps=500.0)])
        r.drives[0]["gone_field"] = 1   # a field an older or newer DriveSpeed had
        r.drives.append({"read_mbps": 3.0})   # no root: skipped
        self.assertEqual([s.root for s in r.speeds()], ["C:\\"])

    def test_lines_and_tags(self):
        with mock.patch.object(features, "app_model_store", return_value=""):
            r = syscheck.recommend(report(), make_profile(Path(".")))
        text = "\n".join(syscheck.lines(r))
        for part in ("This PC: Test GPU, 12.0 GB", "Features:", "Chat model:", "Speech model:",
                     "NVIDIA Canary-Qwen 2.5B: Recommended."):
            self.assertIn(part, text)
        text.encode("cp1252")   # a Windows console prints it
        self.assertEqual(syscheck.tag(r.verdict("dictation.model", CANARY)), "  · recommended")
        self.assertEqual(syscheck.tag(r.verdict("dictation.model", PARAKEET)), "")


class Tray(unittest.TestCase):
    def test_features_card_words_from_the_last_report(self):
        from types import SimpleNamespace

        import tray

        r = syscheck.Report(checked_at=time.time(), verdicts=[
            syscheck.Verdict("images", "", "not_recommended", "Old driver."),
            syscheck.Verdict("chat", "", "recommended", "Yes."),
            syscheck.Verdict("models", "", "recommended", "Required.")])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "check.json"
            syscheck.save(r, path)
            app = SimpleNamespace(check_mtime=0.0, check_report=None)
            S = features.Status
            with mock.patch.object(syscheck, "CHECK_FILE", path):
                word = lambda fid, s: tray.TrayApp._check_word(app, fid, s)  # noqa: E731
                self.assertEqual(word("images", S(True, True, "Installed")), "  ·  not recommended here")
                self.assertEqual(word("chat", S(False, False, "Not installed")), "  ·  recommended here")
                self.assertEqual(word("chat", S(True, True, "Installed")), "")      # installed: nothing to add
                self.assertEqual(word("models", S(True, True, "Installed")), "")    # required: no word
                self.assertEqual(word("openclaw", None), "")                        # no verdict
            with mock.patch.object(syscheck, "CHECK_FILE", Path(d) / "none.json"):
                self.assertEqual(tray.TrayApp._check_word(app, "images", None), "")


class SetupStep(unittest.TestCase):
    def test_reuses_the_installer_s_report_and_warns_about_a_chosen_model(self):
        d = disks.DriveSpeed(root="C:\\", read_mbps=2800.0, write_mbps=2000.0, bus="NVMe", free_gb=200.0,
                             method="test file")
        saved = report(drives=[d], ram=16.0, avail=10.0)
        with tempfile.TemporaryDirectory() as tmp:
            profile = make_profile(Path(tmp), models={**make_profile(Path(tmp))["models"],
                                                      "primary": "qwen3.6:35b-a3b-coding"})
            with mock.patch.object(syscheck, "load", return_value=saved), \
                    mock.patch.object(syscheck, "run") as run, \
                    mock.patch.object(syscheck, "save"), \
                    mock.patch.object(features, "app_model_store", return_value=""), \
                    mock.patch.object(install, "current_tool_dir", return_value="C:\\tools"):
                with self.assertRaises(install.Warn) as w:
                    install.step_disks(install.Plan(model_store="C:\\models"), profile, lambda *a: None)
            run.assert_not_called()   # the drives were not tested again
        self.assertIn("qwen3.6:35b-a3b-coding is not recommended on this PC", str(w.exception))
        self.assertIn("in the installer", str(w.exception))


if __name__ == "__main__":
    unittest.main()
