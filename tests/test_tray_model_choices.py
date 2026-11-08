"""The Settings tab's model lists hold model names only. The context sizes live in the same `models:` section of the
machine file, and once leaked into every model list (16384 and 32768 above qwen3.5:9b)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import tray  # noqa: E402
from stacklib import settings as cfg  # noqa: E402


class Box:
    def __init__(self):
        self.values: list[str] = []

    def configure(self, values):
        self.values = list(values)

    def cget(self, _name):
        return tuple(self.values)


class Var:
    def set(self, value):
        self.value = value


class ModelChoices(unittest.TestCase):
    def _load(self, values, installed):
        boxes = [Box(), Box()]
        app = SimpleNamespace(profile={"name": "x"}, model_boxes=boxes, setting_vars={sid: Var() for sid in values},
                              cloud_label=mock.Mock(), advanced_parts=[], _note_advanced=lambda _p: None,
                              _settings_dirty=lambda: None)
        with mock.patch.object(tray.prof, "resolve_profile", return_value={"name": "x"}), \
                mock.patch.object(tray.usage_log, "configure"), \
                mock.patch.object(cfg, "current_values", return_value=values), \
                mock.patch.object(cfg, "installed_models", return_value=installed):
            tray.TrayApp._load_settings(app)
        return boxes

    def test_context_sizes_stay_out_of_the_model_lists(self):
        values = {"models.primary": "qwen3.5:9b", "models.primary_num_ctx": "32768",
                  "models.small": "qwen3.5:9b", "models.small_num_ctx": "16384"}
        for box in self._load(values, ["qwen3.5:9b", "qwen3.6:35b-a3b-coding"]):
            self.assertEqual(box.values, ["qwen3.5:9b", "qwen3.6:35b-a3b-coding"])

    def test_a_configured_model_that_is_not_pulled_stays_selectable(self):
        values = {"models.primary": "flint:40b-a2b", "models.primary_num_ctx": "32768",
                  "models.small": "qwen3.5:9b", "models.small_num_ctx": "32768"}
        for box in self._load(values, ["qwen3.5:9b"]):
            self.assertEqual(box.values, ["flint:40b-a2b", "qwen3.5:9b"])


if __name__ == "__main__":
    unittest.main()
