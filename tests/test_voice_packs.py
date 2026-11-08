"""Read aloud's voices for more languages: Piper voices from config/installer.yaml voice_packs (stacklib/dictation/speak.py
and tts.py), downloaded and removed through the setup worker (dictation, install.py, uninstall.py), listed by the
installer, the tray and the Storage card. Nothing here downloads, loads a model or touches this PC's voices folder.

Checked by hand on 2026-11-08 with the real voices in read aloud's environment: German, Russian and Vietnamese
sentences made with Thorsten, Dmitri and VAIS-1000, transcribed back by Whisper (small, CPU) word for word for German
and with one word off for Russian and Vietnamese.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import unquote

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from stacklib import catalog, dictation, features, install, storage, uninstall  # noqa: E402
from stacklib.dictation import speak  # noqa: E402


def fake_voice(folder: Path, key: str, size: int = 2000) -> Path:
    d = folder / key
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{key}.onnx").write_bytes(b"x" * size)
    (d / f"{key}.onnx.json").write_text("{}", encoding="utf-8")
    return d


class Catalog(unittest.TestCase):
    def test_every_voice_is_complete_and_open(self):
        packs = catalog.section("voice_packs")
        self.assertRegex(packs["revision"], r"^[0-9a-f]{40}$")
        for key, meta in speak.PIPER_VOICES.items():
            with self.subTest(voice=key):
                self.assertTrue(meta["path"].endswith(key.split("-", 1)[1].replace("-", "/")))
                self.assertIn(meta["language"].split("-")[0], key.lower())
                self.assertGreater(meta["size_mb"], 10)
                self.assertTrue(meta["speakers"])
                self.assertNotIn("NC", str(meta["data_licence"]).upper().replace("NC-", "NC").split("-"))
                self.assertIn("lessac_base", meta)   # the research-only base is stated, either way

    def test_the_languages_kokoro_lacks_are_covered(self):
        families = {speak.family(m["language"]) for m in speak.PIPER_VOICES.values()}
        self.assertTrue({"de", "ru", "vi"} <= families)
        self.assertFalse(families & {"ar", "id", "ja", "zh", "ko", "th", "hi"})   # no clean Piper voice for these


class Voices(unittest.TestCase):
    def test_one_voice_per_speaker_with_its_language(self):
        voices = {v.id: v for v in speak.piper_voices(speak.PIPER_VOICES)}
        self.assertEqual(voices["piper:de_DE-thorsten-high"].label, "Thorsten (German, male, Piper)")
        self.assertEqual({voices["piper:fr_FR-upmc-medium:0"].name, voices["piper:fr_FR-upmc-medium:1"].name},
                         {"Jessica", "Pierre"})
        self.assertEqual(voices["piper:es_AR-daniela-high"].label, "Daniela (Spanish, Argentina, female, Piper)")
        self.assertEqual(speak.piper_key("piper:fr_FR-upmc-medium:1"), ("fr_FR-upmc-medium", 1))
        self.assertEqual(speak.piper_key("piper:de_DE-thorsten-high"), ("de_DE-thorsten-high", 0))

    def test_only_downloaded_voices_are_offered(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(speak.installed_piper_voices(t), [])
            fake_voice(Path(t), "ru_RU-dmitri-medium")
            (Path(t) / "de_DE-thorsten-high").mkdir()   # a download that never finished
            self.assertEqual([v.id for v in speak.installed_piper_voices(t)], ["piper:ru_RU-dmitri-medium"])
            ids = [vid for vid, _label in speak.voice_choices([], packs_dir=t)]
            self.assertIn("piper:ru_RU-dmitri-medium", ids)
            self.assertIn("af_heart", ids)

    def test_auto_language_reads_with_the_new_voices(self):
        voices = speak.kokoro_voices() + speak.piper_voices(speak.PIPER_VOICES)
        cfg = speak.Config(voice="af_heart")
        for text, name in (("Das ist nicht schlecht, aber wir sind noch nicht fertig.", "Thorsten"),
                           ("Сегодня хороший день, и мы читаем этот текст вслух.", "Dmitri"),
                           ("Hôm nay là một ngày đẹp trời và chúng tôi đọc to văn bản này.", "VAIS-1000")):
            with self.subTest(text=text):
                self.assertEqual(speak.pick_voice(cfg, text, voices)[0].name, name)
        # Kokoro keeps the languages it speaks: an Italian text still gets Sara, not Paola.
        self.assertEqual(speak.pick_voice(cfg, "Questa è una prova, e non è la prima volta che la faccio.",
                                          voices)[0].name, "Sara")

    def test_input_ids_follow_piper_phonemize(self):
        ids = speak.piper_ids("ab?", {"_": [0], "^": [1], "$": [2], "a": [5], "b": [6], "?": [9]})
        self.assertEqual(ids, [1, 0, 5, 0, 6, 0, 9, 0, 2])
        self.assertEqual(speak.piper_ids("aXa", {"_": [0], "^": [1], "$": [2], "a": [5]}), [1, 0, 5, 0, 5, 0, 2])

    def test_settings(self):
        warned = []
        cfg = speak.Config.from_profile({"read_aloud": {"packs": ["de_DE-thorsten-high", "xx_XX-nobody-low"]},
                                         "media": {"root": "D:\\media"}}, warn=warned.append)
        self.assertEqual(cfg.packs, ["de_DE-thorsten-high"])
        self.assertEqual(cfg.packs_dir, str(Path("D:\\media") / "voices"))
        self.assertTrue(warned)
        cfg = speak.Config.from_profile({"data_dir": "C:\\app\\.run"})
        self.assertEqual(cfg.packs_dir, str(Path("C:\\app\\.run") / "voices"))


class Downloads(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.profile = {"name": "TESTBOX", "media": {}, "data_dir": str(self.tmp),
                        "read_aloud": {"packs_dir": str(self.tmp / "voices")}}

    def tearDown(self):
        self._tmp.cleanup()

    def test_urls_are_pinned_and_quoted(self):
        url = dictation.pack_url("pt_PT-tugão-medium", "pt_PT-tugão-medium.onnx")
        self.assertIn(catalog.section("voice_packs")["revision"], url)
        self.assertNotIn("ã", url)
        self.assertTrue(unquote(url).endswith("pt/pt_PT/tugão/medium/pt_PT-tugão-medium.onnx"))

    def test_download_fetches_each_file_once(self):
        got = []

        def download(url, dest, report=None):
            got.append(Path(dest).name)
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(b"x")

        with mock.patch("stacklib.media.download", side_effect=download):
            note = dictation.download_packs(self.profile, ["de_DE-thorsten-high"])
            again = dictation.download_packs(self.profile, ["de_DE-thorsten-high"])
        self.assertEqual(got, ["de_DE-thorsten-high.onnx", "de_DE-thorsten-high.onnx.json", "MODEL_CARD"])
        self.assertIn("downloaded de_DE-thorsten-high", note)
        self.assertIn("already there", again)
        self.assertEqual(dictation.installed_packs(self.profile), ["de_DE-thorsten-high"])

    def test_remove_deletes_only_that_voice_and_forgets_it(self):
        folder = self.tmp / "voices"
        fake_voice(folder, "de_DE-thorsten-high")
        keep = fake_voice(folder, "ru_RU-dmitri-medium")
        self.profile["read_aloud"]["packs"] = ["de_DE-thorsten-high", "ru_RU-dmitri-medium"]
        with mock.patch.object(install, "_set_packs") as set_packs:
            note = uninstall.remove_voice_pack(self.profile, "de_DE-thorsten-high")
        self.assertFalse((folder / "de_DE-thorsten-high").exists())
        self.assertTrue(keep.exists())
        set_packs.assert_called_once_with(self.profile, ["ru_RU-dmitri-medium"])
        self.assertIn("deleted de_DE-thorsten-high", note)

    def test_a_folder_that_is_not_a_voice_is_never_deleted(self):
        stray = self.tmp / "voices" / "de_DE-thorsten-high"
        stray.mkdir(parents=True)   # no model in it
        item = uninstall.Item("x", str(stray), 0.0, "pack")
        with self.assertRaises(PermissionError):
            uninstall._check(item, self.profile)

    def test_removing_read_aloud_takes_its_voices(self):
        fake_voice(self.tmp / "voices", "vi_VN-vais1000-medium")
        status = {f.id: features.Status(True, True, "Installed") for f in features.FEATURES}
        with mock.patch.object(uninstall, "_kokoro_item", return_value=None):
            r = uninstall.plan(self.profile, "read_aloud", status)
        self.assertTrue(any(i.kind == "pack" and i.path.endswith("vi_VN-vais1000-medium") for i in r.deletes))
        self.assertIn("VAIS-1000", r.text())

    def test_worker_plans(self):
        plan = install.Plan(model_store="x", remove=["chat"], remove_voices=["ru_RU-dmitri-medium"],
                            voice_packs=["de_DE-thorsten-high"], only=[])
        self.assertEqual([sid for sid, _t, _f in install.plan_steps(plan)],
                         ["remove_chat", "remove_voices", "voice_packs"])
        with mock.patch.object(install, "spawn_worker", return_value=3) as spawn:
            install.start_voice_packs(self.profile, download=["de_DE-thorsten-high"])
        p = spawn.call_args.args[0]
        self.assertEqual((p.voice_packs, p.targets, p.only), (["de_DE-thorsten-high"], ["read_aloud"], []))

    def test_estimate_and_storage_count_them(self):
        hw = features.Hardware(vram_gb=12, desktop_vram_gb=1, ram_gb=32, threads=12)
        with mock.patch.object(features, "_kokoro_cached", return_value=True):
            base = features.estimate("read_aloud", {"read_aloud": {"kokoro": "fp32", "device": "cpu"}}, hw)
            more = features.estimate("read_aloud", {"read_aloud": {"kokoro": "fp32", "device": "cpu",
                                                                   "packs": ["de_DE-thorsten-high"]}}, hw)
        self.assertAlmostEqual(more.disk_gb - base.disk_gb, 0.114)
        fake_voice(self.tmp / "voices", "de_DE-thorsten-high", size=5_000_000)
        out: list = []
        storage._voices(self.profile, out)
        self.assertEqual([(e.name, e.bytes) for e in out], [("Thorsten (German)", 5_000_002)])


class Installer(unittest.TestCase):
    def test_save_features_writes_the_chosen_voices(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "TESTBOX.yaml"
            f.write_text("name: TESTBOX\nread_aloud:\n  enabled: true\n", encoding="utf-8")
            p = {"name": "TESTBOX", "read_aloud": {"enabled": True}, "services": {}, "observability": {}}
            status = {"read_aloud": features.Status(True, True, "Installed")}
            with mock.patch("stacklib.profile.machine_file", return_value=f):
                install.save_features(p, {"read_aloud", "voice_typing"}, status=status, packs=["vi_VN-vais1000-medium"])
            import yaml

            self.assertEqual(yaml.safe_load(f.read_text(encoding="utf-8"))["read_aloud"]["packs"],
                             ["vi_VN-vais1000-medium"])


if __name__ == "__main__":
    unittest.main()
