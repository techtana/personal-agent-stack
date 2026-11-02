"""Tests for the drive speed check (stacklib/disks.py) and the installer steps that use it or were added with it.

Run with `uv run python -m unittest discover -s tests`.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import disks, install  # noqa: E402

# `winsat disk -drive d` on SEKAIHOME, 2026-11-01, with the USB-C plug the wrong way round (USB 2.0 link)
WINSAT_D = """> Disk  Random 16.0 Read                       40.82 MB/s          6.3
> Disk  Sequential 64.0 Read                   41.57 MB/s          5.1
> Disk  Sequential 64.0 Write                  41.67 MB/s          5.1
> Average Read Time with Sequential Writes     0.721 ms          7.8
"""


def drive(root, read, bus="", free=500.0, write=None):
    return disks.DriveSpeed(root=root, read_mbps=read, write_mbps=write or read, bus=bus, free_gb=free, method="test file")


class ParseWinsat(unittest.TestCase):
    def test_reads_the_three_disk_lines(self):
        self.assertEqual(disks.parse_winsat(WINSAT_D), {"random read": 40.82, "seq read": 41.57, "seq write": 41.67})

    def test_no_output_without_admin_gives_nothing(self):
        self.assertEqual(disks.parse_winsat(""), {})


class Advise(unittest.TestCase):
    def test_usb2_speed_warns_with_the_port_and_cable_hint_and_suggests_the_fast_drive(self):
        speeds = [drive("C:\\", 2800, "NVMe", free=150), drive("D:\\", 41, "USB", free=800)]
        warnings, suggestion = disks.advise(speeds, "D:\\ollama\\models", "C:\\uv\\tools", 7.9)
        self.assertEqual(len(warnings), 1)
        self.assertIn("D: reads at only 41 MB/s", warnings[0])
        self.assertIn("USB-C plug", warnings[0])
        self.assertIn("C: would load them faster", suggestion)

    def test_usb3_speed_is_fine_for_models(self):
        speeds = [drive("C:\\", 2800, "NVMe"), drive("D:\\", 376, "USB")]
        self.assertEqual(disks.advise(speeds, "D:\\ollama\\models", "C:\\uv\\tools", 7.9), ([], ""))

    def test_slow_models_drive_with_no_better_drive_says_so(self):
        speeds = [drive("C:\\", 2800, "NVMe", free=10), drive("D:\\", 150, "USB")]
        warnings, suggestion = disks.advise(speeds, "D:\\ollama\\models", "C:\\uv\\tools", 7.9)
        self.assertEqual(warnings, [])
        self.assertIn("D: works", suggestion)

    def test_tools_on_a_usb_drive_warn(self):
        speeds = [drive("C:\\", 2800, "NVMe"), drive("D:\\", 376, "USB")]
        warnings, _ = disks.advise(speeds, "C:\\ollama\\models", "D:\\uv\\tools", 7.9)
        self.assertTrue(any("start at login" in w for w in warnings))

    def test_unmeasured_drive_is_not_judged(self):
        speeds = [disks.DriveSpeed(root="D:\\", error="too little free space for the test file")]
        self.assertEqual(disks.advise(speeds, "D:\\ollama\\models", "", 7.9), ([], ""))


class WinsatHowto(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "winsat is Windows only")
    def test_names_each_test_file_drive_and_the_thresholds(self):
        speeds = [drive("C:\\", 2800), drive("D:\\", 41)]
        speeds[0].method = "winsat"
        lines = disks.winsat_howto(speeds)
        self.assertIn("winsat disk -drive d", lines[0])
        self.assertNotIn("-drive c", lines[0])
        self.assertIn("administrator", lines[0])
        self.assertIn("200 MB/s or more", lines[1])

    def test_nothing_when_winsat_measured_everything(self):
        s = drive("C:\\", 2800)
        s.method = "winsat"
        self.assertEqual(disks.winsat_howto([s]), [])


class FileTest(unittest.TestCase):
    def test_measures_and_cleans_up(self):
        root = Path(tempfile.gettempdir()).anchor
        before = set(Path(tempfile.gettempdir()).glob("agent-stack-speedtest-*"))
        read, write = disks.file_test(root, mb=8)
        self.assertGreater(read, 0)
        self.assertGreater(write, 0)
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("agent-stack-speedtest-*")), before)


class NodeForOpenClaw(unittest.TestCase):
    def test_engine_range(self):
        ok = install.node_ok_for_openclaw
        self.assertFalse(ok((24, 20, 0)))   # what SEKAIHOME had on 2026-11-01
        self.assertTrue(ok((24, 22, 1)))
        self.assertFalse(ok((25, 1, 0)))
        self.assertFalse(ok((26, 12, 0)))
        self.assertTrue(ok((26, 13, 0)))
        self.assertFalse(ok(None))

    def test_version_parse(self):
        self.assertEqual(install._version("v24.20.0\n"), (24, 20, 0))


class HuggingFaceStep(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "the drive-root default is Windows only")
    def test_default_sits_next_to_the_models(self):
        self.assertEqual(install.default_hf_home("D:\\ollama\\models"), "D:\\huggingface")

    def test_moves_the_old_cache_and_sets_hf_home(self):
        with tempfile.TemporaryDirectory() as d:
            old, new = Path(d) / "old", Path(d) / "new"
            (old / "hub" / "models--x").mkdir(parents=True)
            (old / "hub" / "models--x" / "w.bin").write_text("w")
            (old / "token").write_text("secret")
            tool_dir = Path(d) / "tools"
            (tool_dir / "huggingface-hub").mkdir(parents=True)
            (tool_dir / "huggingface-hub" / "pyvenv.cfg").write_text("")
            set_env = {}
            with mock.patch.dict(os.environ, {"HF_HOME": str(old)}), \
                    mock.patch.object(install, "_set_persistent_env", side_effect=set_env.__setitem__), \
                    mock.patch.object(install, "current_tool_dir", return_value=str(tool_dir)):
                detail = install.step_huggingface(install.Plan(model_store=d, hf_home=str(new)), {}, lambda *a: None)
            self.assertTrue((new / "hub" / "models--x" / "w.bin").exists())
            self.assertTrue((old / "token").exists(), "the token is not moved")
        self.assertEqual(set_env["HF_HOME"], str(new))
        self.assertIn("already installed", detail)


class WarningStatus(unittest.TestCase):
    def test_a_warning_does_not_fail_setup(self):
        def warns(plan, profile, report):
            raise install.Warn("D: reads at only 41 MB/s")

        with tempfile.TemporaryDirectory() as d, mock.patch.object(install.prof, "resolve_profile", return_value={}), \
                mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            state_file = Path(d) / "state.json"
            result = install.run(install.Plan(model_store=d), state_file, (("disks", "Check drive speed", warns),))
            state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertTrue(result)
        self.assertEqual(state["steps"][0]["status"], "warning")
        self.assertEqual(state["status"], "warnings")
        self.assertEqual(install.summary(state), "Setup finished with warnings.")


if __name__ == "__main__":
    unittest.main()
