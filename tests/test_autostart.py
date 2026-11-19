"""Tests for "Start with the tray": which services the tray starts when it starts (stacklib/services.py autostart)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import profile as prof, services  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
MACHINE = """name: TESTBOX
services:
  open_webui: native   # the chat
"""


class AutostartTests(unittest.TestCase):
    def test_every_service_starts_by_default(self):
        defaults = yaml.safe_load((REPO / "machines" / "_defaults.yaml").read_text(encoding="utf-8"))
        self.assertEqual(set(defaults["autostart"]), set(services.SERVICE_ORDER))
        self.assertTrue(all(v is True for v in defaults["autostart"].values()))
        self.assertTrue(services.starts_with_tray({}, "litellm"))

    def test_unticked_services_are_left_out_in_order(self):
        p = {"autostart": {"open_webui": False, "comfyui": None, "dictation": "no"}}
        managed = ["litellm", "orchestrator", "comfyui", "open_webui", "dictation"]
        self.assertEqual(services.autostart_services(p, managed), ["litellm", "orchestrator", "comfyui", "dictation"])

    def test_set_autostart_writes_the_machine_file_and_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "TESTBOX.yaml"
            f.write_text(MACHINE, encoding="utf-8")
            p = {"name": "TESTBOX", "autostart": {"open_webui": True}}
            with mock.patch.object(prof, "machine_file", return_value=f):
                services.set_autostart(p, "open_webui", False)
                services.set_autostart(p, "comfyui", False)
                services.set_autostart(p, "comfyui", True)
            text = f.read_text(encoding="utf-8")
            self.assertIn("open_webui: native   # the chat", text)
            self.assertEqual(yaml.safe_load(text)["autostart"], {"open_webui": False, "comfyui": True})
            self.assertEqual(p["autostart"], {"open_webui": False, "comfyui": True})

    def test_set_autostart_refuses_an_unknown_service(self):
        with self.assertRaises(ValueError):
            services.set_autostart({"name": "TESTBOX"}, "ollama", False)

    def test_profile_merges_the_machine_over_the_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "TESTBOX.yaml"
            f.write_text(MACHINE + "autostart:\n  phoenix: false\n", encoding="utf-8")
            with mock.patch.object(prof, "machine_file", return_value=f):
                p = prof.resolve_profile("TESTBOX")
        self.assertFalse(services.starts_with_tray(p, "phoenix"))
        self.assertTrue(services.starts_with_tray(p, "litellm"))


if __name__ == "__main__":
    unittest.main()
