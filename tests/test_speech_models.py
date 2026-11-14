"""Speech-to-text models besides Whisper (config/installer.yaml speech_to_text): NVIDIA Parakeet TDT through onnx-asr and
Canary-Qwen 2.5B through transcribe.cpp (stacklib/dictation/stt.py), how voice typing's Engine picks the GPU or the CPU
for them, and what the installer, the tray and the removal plan say about them. The engines themselves are not in the
project environment: fake backends stand in for them; the real ones ran on the reference PC (memory/state.md, item 41).
The classes marked NUMPY need numpy (stt.py and the Engine), which only voice typing's environment has: run them there
with `<voice typing env>/Scripts/python.exe -m unittest tests.test_speech_models`.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import dictation, features, gpu_models, settings, uninstall  # noqa: E402
from stacklib.dictation import Config, models  # noqa: E402

HAS_NUMPY = importlib.util.find_spec("numpy") is not None
NUMPY = unittest.skipUnless(HAS_NUMPY, "stt.py and the Engine need numpy (voice typing's environment)")
if HAS_NUMPY:
    import numpy as np

    from stacklib.dictation import engine as engine_mod, stt

RATE = 16000
PARAKEET, CANARY = "parakeet-tdt-0.6b-v3", "canary-qwen-2.5b"


def tone(seconds: float, level: float = 0.2):
    t = np.arange(int(seconds * RATE)) / RATE
    return (np.sin(2 * np.pi * 220 * t) * level).astype(np.float32)


def quiet(seconds: float):
    return np.zeros(int(seconds * RATE), np.float32)


class Catalog(unittest.TestCase):
    def test_the_new_models_and_what_they_speak(self):
        p, c = models.SPEECH[PARAKEET], models.SPEECH[CANARY]
        self.assertEqual((p.engine, p.device, p.family), ("onnx-asr", "cpu", "Parakeet"))
        self.assertEqual((c.engine, c.device, c.family), ("transcribe.cpp", "gpu", "Canary-Qwen"))
        self.assertEqual(models.SPEECH["large-v3"].family, "Whisper")
        self.assertTrue(p.speaks("de") and p.speaks("auto") and not p.speaks("th"))
        self.assertTrue(c.speaks("en") and not c.speaks("de"))
        self.assertTrue(models.english_only(CANARY))
        self.assertEqual(len(models.languages_for(PARAKEET)), 26)   # detection and 25 languages
        self.assertEqual(models.languages_for(PARAKEET)[0], models.AUTO)
        self.assertEqual(len(models.languages_for("large-v3")), 101)
        self.assertEqual(c.model_file, "canary-qwen-2.5b-Q8_0.gguf")
        self.assertIn(c.model_file, c.files)
        self.assertEqual(models.engine_of("tiny"), "faster-whisper")   # a name typed into the machine file
        self.assertEqual(models.speech_model("tiny").repo, "Systran/faster-whisper-tiny")

    def test_installer_labels(self):
        self.assertEqual(features.speech_choice_label(PARAKEET), "NVIDIA Parakeet TDT 0.6B v3 (0.7 GB, CPU, 25 languages)")
        self.assertEqual(features.speech_choice_label(CANARY), "NVIDIA Canary-Qwen 2.5B (2.8 GB, English)")
        self.assertEqual(features.speech_choice_label("large-v3"), "Whisper large-v3 (3.1 GB)")
        opts = dict((o.key, fn) for o, fn in features.OPTIONS["voice_typing"])
        self.assertEqual([v for v, _ in opts["model"]({})], models.CHOICES)


@NUMPY
class Split(unittest.TestCase):
    def test_short_audio_comes_back_whole(self):
        a = tone(10)
        self.assertEqual(len(stt.split(a)), 1)

    def test_long_audio_is_cut_in_its_pauses(self):
        a = np.concatenate([tone(20), quiet(0.6), tone(15), quiet(0.6), tone(22)])
        pieces = stt.split(a)
        self.assertGreater(len(pieces), 1)
        self.assertEqual(sum(len(p) for p in pieces), len(a))
        self.assertTrue(all(len(p) <= stt.MAX_PIECE_S * RATE for p in pieces))
        first = len(pieces[0]) / RATE
        self.assertAlmostEqual(first, 20.3, delta=0.35)   # inside the first pause, not at 25 s

    def test_silence(self):
        self.assertTrue(stt.is_silent(quiet(2)))
        self.assertTrue(stt.is_silent(tone(2, level=0.0005)))   # -69 dBFS
        self.assertFalse(stt.is_silent(np.concatenate([quiet(2), tone(0.3)])))


class FakeBackend:
    """Stands in for stt.Backend (made one below, once stt can be imported)."""

    def __init__(self, m, on_gpu, threads, log=print):
        self.m = m
        self.device = ("vulkan" if m.engine == "transcribe.cpp" else "cuda") if on_gpu else "cpu"
        self.calls, self.closed = [], False

    def transcribe(self, audio, language):
        self.calls.append((len(audio), language))
        return f"piece {len(self.calls)}", "en" if self.m.engine == "transcribe.cpp" else "", 3

    def close(self):
        self.closed = True


if HAS_NUMPY:
    FakeBackend = type("FakeBackend", (FakeBackend, stt.Backend), {})


@NUMPY
class Transcribe(unittest.TestCase):
    def test_pieces_are_joined_and_silent_ones_skipped(self):
        b = FakeBackend(models.SPEECH[CANARY], True, 2)
        a = np.concatenate([tone(20), quiet(0.6), quiet(24), quiet(0.5), tone(5)])
        text, lang, tokens = stt.transcribe(b, a, "en")
        self.assertEqual(text, " ".join(f"piece {i + 1}" for i in range(len(b.calls))))
        self.assertLess(len(b.calls), len(stt.split(a)))   # the silent piece was not sent
        self.assertEqual((lang, tokens), ("en", 3 * len(b.calls)))


class Files(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.home, ignore_errors=True))
        self.m = models.SPEECH[PARAKEET]

    def snapshot(self):
        return stt.snapshot_dir(self.m, self.home)

    def test_missing_files_and_cache_check(self):
        profile = {"media": {"hf_home": str(self.home)}}
        self.assertFalse(dictation.model_cached(profile, PARAKEET))
        snap = self.home / "hub" / f"models--{self.m.repo.replace('/', '--')}" / "snapshots" / self.m.revision
        snap.mkdir(parents=True)
        for name in self.m.files:
            (snap / name).write_bytes(b"x")
        self.assertTrue(dictation.model_cached(profile, PARAKEET))
        if HAS_NUMPY:
            self.assertEqual(stt.snapshot_dir(self.m, self.home), snap)
            self.assertEqual(stt.missing_files(self.m, self.home), [])
        (snap / "vocab.txt").unlink()
        self.assertFalse(dictation.model_cached(profile, PARAKEET))

    @NUMPY
    def test_fetch_checks_each_pinned_sha256(self):
        good = b"weights"
        m = models.SpeechModel(name="t", label="Test", engine="onnx-asr", repo="org/repo", revision="a" * 40,
                               files={"a.onnx": hashlib.sha256(good).hexdigest(), "vocab.txt": ""})

        def download(repo, name, revision):
            path = stt.snapshot_dir(m, self.home) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(good if name == "a.onnx" else b"words")
            return str(path)

        hub = mock.MagicMock(hf_hub_download=download)
        with mock.patch.dict(sys.modules, {"huggingface_hub": hub}), \
                mock.patch.object(stt, "hf_home", return_value=self.home):
            self.assertEqual(stt.fetch(m), stt.snapshot_dir(m, self.home))
            bad = models.SpeechModel(**{**m.__dict__, "files": {"a.onnx": "0" * 64}})
            (stt.snapshot_dir(m, self.home) / "a.onnx").unlink()
            with self.assertRaises(stt.SttError):
                stt.fetch(bad)
            self.assertFalse((stt.snapshot_dir(m, self.home) / "a.onnx").exists())   # deleted, to download again


@NUMPY
class EngineChoice(unittest.TestCase):
    """Where Engine runs each model (engine.Engine._open): no real model loads; open_backend and Whisper are fakes."""

    def engine(self, model, device="auto", fail_gpu=False):
        cfg = Config(model=model, device=device, cpu_model="small", unload_after_min=0)
        e = engine_mod.Engine(cfg, log=lambda _m: None)
        opened = []

        def open_backend(m, on_gpu, threads, log=print):
            opened.append((m.name, on_gpu))
            if on_gpu and fail_gpu:
                raise stt.SttError("no Vulkan device")
            return FakeBackend(m, on_gpu, threads)

        whisper = mock.Mock(name="WhisperModel")
        whisper.transcribe.return_value = (iter(()), mock.Mock(language="en"))
        patches = [mock.patch.object(stt, "open_backend", side_effect=open_backend),
                   mock.patch.object(engine_mod.Engine, "_model", return_value=whisper)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return e, opened

    def test_parakeet_runs_on_the_cpu_by_itself(self):
        e, opened = self.engine(PARAKEET)
        self.assertTrue(e.wait_ready(5))
        self.assertEqual((e.device, e.model_name, e.note, opened), ("cpu", PARAKEET, "", [(PARAKEET, False)]))
        self.assertTrue(e.previews)   # quick enough on the CPU for previews while you speak

    def test_parakeet_on_cuda_when_asked(self):
        e, opened = self.engine(PARAKEET, device="cuda")
        self.assertTrue(e.wait_ready(5))
        self.assertEqual((e.device, opened), ("cuda", [(PARAKEET, True)]))

    def test_canary_runs_on_the_gpu_through_vulkan(self):
        e, opened = self.engine(CANARY)
        self.assertTrue(e.wait_ready(5))
        self.assertEqual((e.device, opened), ("vulkan", [(CANARY, True)]))
        self.assertTrue(e.previews)
        self.assertEqual(e.family, "Canary-Qwen")

    def test_canary_without_a_gpu_gives_way_to_the_cpu_model(self):
        e, opened = self.engine(CANARY, fail_gpu=True)
        self.assertTrue(e.wait_ready(5))
        self.assertEqual((e.device, e.model_name), ("cpu", "small"))   # 2x real time on the CPU is too slow
        self.assertIn("GPU not used: no Vulkan device", e.note)
        self.assertFalse(e.previews)   # Whisper on the CPU: no previews

    def test_a_native_error_on_the_gpu_falls_back_to_the_cpu(self):
        e, opened = self.engine(CANARY)
        self.assertTrue(e.wait_ready(5))
        e.model.transcribe = mock.Mock(side_effect=ValueError("out of device memory"))
        with mock.patch.object(engine_mod.usage_log, "record"):
            text, _ = e.transcribe(tone(3), language="")
        self.assertEqual((e.device, e.model_name), ("cpu", "small"))   # Canary on the CPU is too slow: Whisper small
        self.assertEqual(opened, [(CANARY, True)])

    def test_a_forced_gpu_that_fails_fails(self):
        e, _ = self.engine(CANARY, device="cuda", fail_gpu=True)
        self.assertFalse(e.wait_ready(5))
        self.assertIn("Canary-Qwen could not load", e.note)

    def test_decode_records_and_unload_closes(self):
        e, _ = self.engine(CANARY)
        records = []
        with mock.patch.object(engine_mod.usage_log, "record", side_effect=lambda *a, **k: records.append((a, k))):
            text, lang = e.transcribe(tone(3), language="")
        self.assertEqual((text, lang), ("piece 2", "en"))   # call 1 was the warm-up at load
        self.assertEqual(e.model.calls[0], (RATE, None))
        args, kw = records[-1]
        self.assertEqual((args[1], kw["output_tokens"], kw["detail"]["device"]), (CANARY, 3, "vulkan"))
        backend = e.model
        e.unload()
        self.assertTrue(backend.closed)
        self.assertIsNone(e.model)


class InstallAndStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.profile = {"name": "TESTBOX", "dictation": {"model": CANARY, "cpu_model": "small",
                                                         "env_dir": str(self.tmp / "dictation")},
                        "services": {"dictation": "native"}, "media": {}, "data_dir": self.tmp}
        site = self.tmp / "dictation" / ".venv" / "Lib" / "site-packages"
        (site / "faster_whisper").mkdir(parents=True)
        (site / "faster_whisper" / "__init__.py").write_text("", encoding="utf-8")
        py = dictation.env_python(self.profile)
        py.parent.mkdir(parents=True, exist_ok=True)
        py.write_text("", encoding="utf-8")
        self.site = site

    def test_engines_the_chosen_models_need(self):
        self.assertEqual(dictation.wanted_engines(self.profile), ["transcribe.cpp"])
        self.assertEqual(dictation.missing_engines(self.profile), ["transcribe.cpp"])
        (self.site / "transcribe_cpp").mkdir()
        (self.site / "transcribe_cpp" / "__init__.py").write_text("", encoding="utf-8")
        self.assertEqual(dictation.missing_engines(self.profile), [])
        whisper_only = {**self.profile, "dictation": {**self.profile["dictation"], "model": "large-v3-turbo"}}
        self.assertEqual(dictation.wanted_engines(whisper_only), [])

    def test_status_says_model_missing_until_the_engine_is_there(self):
        with mock.patch.object(dictation, "hotkey_label", return_value="Ctrl+Alt+D"):
            s = features._status_voice_typing(self.profile)
            self.assertEqual((s.installed, s.state, s.level), (False, "Model missing", "warn"))
            self.assertIn("transcribe.cpp", s.detail)
            (self.site / "transcribe_cpp").mkdir()
            (self.site / "transcribe_cpp" / "__init__.py").write_text("", encoding="utf-8")
            s = features._status_voice_typing(self.profile)
        self.assertEqual((s.installed, s.state), (True, "Installed"))
        self.assertIn("NVIDIA Canary-Qwen 2.5B runs from", s.detail)

    def test_settings_start_the_install_for_a_missing_engine(self):
        logs = []
        with mock.patch("stacklib.install.start_feature", return_value=12) as start:
            settings._install_speech_engine(self.profile, {"dictation.model"}, logs.append)
            start.assert_called_once_with(self.profile, "voice_typing")
            settings._install_speech_engine(self.profile, {"dictation.hotkey"}, logs.append)   # not a model change
            self.assertEqual(start.call_count, 1)
        self.assertIn("Installing transcribe.cpp for NVIDIA Canary-Qwen 2.5B", logs[0])
        (self.site / "transcribe_cpp").mkdir()
        (self.site / "transcribe_cpp" / "__init__.py").write_text("", encoding="utf-8")
        with mock.patch("stacklib.install.start_feature", return_value=12) as start, \
                mock.patch.object(dictation, "model_cached", return_value=False):
            settings._install_speech_engine(self.profile, {"dictation.model"}, logs.append)   # engine there, files not
            start.assert_called_once()
        with mock.patch("stacklib.install.start_feature") as start, \
                mock.patch.object(dictation, "model_cached", return_value=True):
            settings._install_speech_engine(self.profile, {"dictation.model"}, logs.append)
            start.assert_not_called()


class Estimates(unittest.TestCase):
    def hw(self, vram=12.0):
        return features.Hardware(gpu="GPU", vram_gb=vram, desktop_vram_gb=1.0 if vram else 0.0, ram_gb=32, threads=12)

    def profile(self, model, device="auto"):
        return {"dictation": {"model": model, "device": device, "cpu_model": "small"}, "models": {}, "media": {}}

    def estimate(self, model, vram=12.0, device="auto"):
        with mock.patch.object(features, "_whisper_cached", return_value=False):
            return features.estimate("voice_typing", self.profile(model, device), self.hw(vram))

    def test_parakeet_holds_no_gpu_memory(self):
        e = self.estimate(PARAKEET)
        self.assertEqual(e.vram_gb, 0.0)
        self.assertTrue(e.cpu_bursts)
        self.assertAlmostEqual(e.ram_gb, features.catalog.feature_footprint("voice_typing")["ram_gb"] + 1.1)
        self.assertIn("25 European languages", e.note)
        self.assertEqual(e.shared[0][:2], (f"speech:{PARAKEET}", 0.67))

    def test_canary_on_the_gpu_and_without_one(self):
        e = self.estimate(CANARY)
        self.assertEqual((e.vram_gb, e.gpu_short), (3.3, "~0.6 s per phrase"))
        self.assertIn("Canary-Qwen loads on first use", e.held)
        self.assertIn("Vulkan shaders", e.note)
        cpu = self.estimate(CANARY, vram=0.0)
        self.assertEqual(cpu.vram_gb, 0.0)
        self.assertIn("gives way to Whisper small", cpu.note)
        self.assertEqual(features.speech_run(self.profile(CANARY), self.hw(0.0))[0].name, "small")

    def test_turbo_stays_as_measured(self):
        e = self.estimate("large-v3-turbo")
        self.assertEqual((e.vram_gb, e.gpu_short), (1.2, "~0.6 s per phrase"))
        self.assertIn("0.3-0.6 s per phrase with large-v3-turbo", e.basis)


class TrayAndRemoval(unittest.TestCase):
    def test_gpu_card_row_for_canary_on_vulkan(self):
        row = gpu_models._whisper_row({"engine": "ready", "model": CANARY, "device": "vulkan"})
        self.assertEqual((row["name"], row["gpu"]), (CANARY, "100%"))
        self.assertAlmostEqual(row["bytes"] / 2 ** 30, 3.3, places=2)
        cpu = gpu_models._whisper_row({"engine": "ready", "model": PARAKEET, "device": "cpu"})
        self.assertEqual((cpu["bytes"], cpu["gpu"]), (0, "CPU"))

    def test_removal_names_the_speech_model(self):
        home = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(home, ignore_errors=True))
        profile = {"media": {"hf_home": str(home)}, "dictation": {"model": PARAKEET, "cpu_model": "small"}}
        repo_dir = uninstall.hf_repo_dir(profile, models.SPEECH[PARAKEET].repo)
        repo_dir.mkdir(parents=True)
        (repo_dir / "x.onnx").write_bytes(b"0" * 10)
        items = uninstall._whisper_items(profile, "voice_typing", set())
        self.assertEqual([i.what for i in items], ["Speech model NVIDIA Parakeet TDT 0.6B v3"])


if __name__ == "__main__":
    unittest.main()
