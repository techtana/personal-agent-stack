r"""The Ollama app's own Model location overrides OLLAMA_MODELS (seen 2026-11-08: setup wrote ~/.ollama/models, the app
kept D:\ollama\models, the pulls went there and the tray said "Models missing")."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from stacklib import features, install, ollama  # noqa: E402


def settings_db(folder: Path, models: str | None, table: bool = True) -> Path:
    db = folder / "db.sqlite"
    con = sqlite3.connect(db)
    if table:
        con.execute("CREATE TABLE settings (id INTEGER PRIMARY KEY, device_id TEXT, models TEXT, agent INTEGER)")
        con.execute("INSERT INTO settings (device_id, models, agent) VALUES ('x', ?, 0)", (models,))
    con.commit()
    con.close()
    return db


def profile(store: str) -> dict:
    return {"name": "TEST", "model_store": store, "ollama_env": {"OLLAMA_MODELS": store}, "ports": {"ollama": 1},
            "models": {"embed": "nomic-embed-text", "primary": "qwen3.5:9b"}}


class AppSetting(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_reads_the_model_location(self):
        self.assertEqual(ollama.app_model_location(settings_db(self.tmp, r"D:\ollama\models ")), r"D:\ollama\models")

    def test_unset_missing_or_foreign_database_reads_as_none(self):
        self.assertEqual(ollama.app_model_location(settings_db(self.tmp, "")), "")
        self.assertEqual(ollama.app_model_location(self.tmp / "absent.sqlite"), "")
        other = self.tmp / "other"
        other.mkdir()
        self.assertEqual(ollama.app_model_location(settings_db(other, None, table=False)), "")

    def test_tags_names_include_the_short_form_of_latest(self):
        with mock.patch.object(ollama, "api", return_value={"models": [{"name": "nomic-embed-text:latest"},
                                                                       {"name": "qwen3.5:9b"}]}):
            self.assertEqual(ollama.model_names("http://x"),
                             {"nomic-embed-text:latest", "nomic-embed-text", "qwen3.5:9b"})
        with mock.patch.object(ollama, "api", side_effect=OSError("refused")):
            self.assertIsNone(ollama.model_names("http://x"))


class Status(unittest.TestCase):
    def test_running_ollama_decides_what_is_missing(self):
        p = profile(r"C:\nowhere\models")   # no manifests there; Ollama has them in another folder
        with mock.patch.object(features, "ollama_models", return_value={"nomic-embed-text", "qwen3.5:9b"}), \
                mock.patch.object(features, "which", return_value="ollama"):
            self.assertEqual(features.missing_models(p), [])
            self.assertTrue(features._status_models(p).installed)
        with mock.patch.object(features, "ollama_models", return_value={"qwen3.5:9b"}):
            self.assertEqual(features.missing_models(p), ["nomic-embed-text"])

    def test_with_ollama_off_the_app_folder_is_searched(self):
        with tempfile.TemporaryDirectory() as d:
            for m in ("nomic-embed-text", "qwen3.5:9b"):
                path = features.manifest_path(d, m)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}")
            p = profile(str(Path(d) / "elsewhere"))
            self.assertEqual(features.missing_models(p), ["nomic-embed-text", "qwen3.5:9b"])
            with mock.patch.object(features, "app_model_store", return_value=d):
                self.assertEqual(features.missing_models(p), [])

    def test_override_shows_on_the_row(self):
        p = profile(r"C:\models")
        with mock.patch.object(features, "app_model_store", return_value=r"D:\ollama\models"), \
                mock.patch.object(features, "ollama_models", return_value={"nomic-embed-text", "qwen3.5:9b"}), \
                mock.patch.object(features, "which", return_value="ollama"):
            s = features._status_models(p)
        self.assertTrue(s.installed)
        self.assertEqual(s.level, "warn")
        self.assertIn(r"Model location is D:\ollama\models", s.detail)
        with mock.patch.object(features, "app_model_store", return_value=r"C:\models"):
            self.assertEqual(features.store_override_note(p), "")


class Installer(unittest.TestCase):
    def test_models_folder_must_match_the_app_setting(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(features, "app_model_store", return_value=str(Path(d) / "app")):
            self.assertFalse(install.check_dir(str(Path(d) / "mine"), 0.0, models=True).ok)
            self.assertTrue(install.check_dir(str(Path(d) / "app"), 0.0, models=True).ok)
            self.assertTrue(install.check_dir(str(Path(d) / "mine"), 0.0).ok)   # other folders are not Ollama's

    def test_env_step_warns_and_move_step_keeps_files(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst, app = (str(Path(d) / n) for n in ("old", "new", "app"))
            plan = install.Plan(model_store=dst, move_models_from=src)
            with mock.patch.object(features, "app_model_store", return_value=app), \
                    mock.patch.object(install, "has_models", return_value=True), \
                    mock.patch.object(install.ollama, "stop") as stop:
                with self.assertRaises(install.Warn):
                    install.step_models_move(plan, profile(dst), lambda *a: None)
                stop.assert_not_called()
            with mock.patch.object(features, "app_model_store", return_value=app), \
                    mock.patch.object(install, "which", return_value="ollama"), \
                    mock.patch.object(install.ollama, "set_user_env", return_value=[]), \
                    mock.patch.object(install.ollama, "version", return_value="0.40"):
                with self.assertRaises(install.Warn) as cm:
                    install.step_ollama_env(install.Plan(model_store=dst), profile(dst), lambda *a: None)
            self.assertIn(app, str(cm.exception))


if __name__ == "__main__":
    unittest.main()
