"""Tests for where the machine profile lives (stacklib/profile.py): local to the computer, shared with worktrees.

Run with `uv run python -m unittest discover -s tests`.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import profile as prof  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


class MachineFileTest(unittest.TestCase):
    def setUp(self):
        prof._main_checkout.cache_clear()
        self.addCleanup(prof._main_checkout.cache_clear)

    def test_own_profile_wins(self):
        with tempfile.TemporaryDirectory() as here, tempfile.TemporaryDirectory() as main:
            Path(here, "BOX.yaml").write_text("name: BOX\n", encoding="utf-8")
            (Path(main) / "machines").mkdir()
            Path(main, "machines", "BOX.yaml").write_text("name: BOX\n", encoding="utf-8")
            with mock.patch.object(prof, "MACHINES_DIR", Path(here)), \
                    mock.patch.object(prof, "_main_checkout", return_value=Path(main)):
                self.assertEqual(prof.machine_file("BOX"), Path(here, "BOX.yaml"))

    def test_worktree_without_profile_uses_the_main_checkouts(self):
        with tempfile.TemporaryDirectory() as here, tempfile.TemporaryDirectory() as main:
            (Path(main) / "machines").mkdir()
            Path(main, "machines", "BOX.yaml").write_text("name: BOX\nos: windows\n", encoding="utf-8")
            with mock.patch.object(prof, "MACHINES_DIR", Path(here)), \
                    mock.patch.object(prof, "_main_checkout", return_value=Path(main)):
                self.assertEqual(prof.machine_file("BOX"), Path(main, "machines", "BOX.yaml"))
                self.assertEqual(prof.load_machine("BOX")["os"], "windows")

    def test_missing_everywhere_points_at_this_checkout(self):
        with tempfile.TemporaryDirectory() as here:
            with mock.patch.object(prof, "MACHINES_DIR", Path(here)), \
                    mock.patch.object(prof, "_main_checkout", return_value=None):
                self.assertEqual(prof.machine_file("BOX"), Path(here, "BOX.yaml"))
                self.assertEqual(prof.load_machine("BOX"), {})

    def test_main_checkout_is_none_in_the_main_checkout(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(prof, "REPO", Path(d)), \
                mock.patch.object(prof.subprocess, "run") as run:
            run.return_value.stdout = str(Path(d) / ".git") + "\n"
            self.assertIsNone(prof._main_checkout())
            prof._main_checkout.cache_clear()
            run.return_value.stdout = str(Path(d).parent / "main" / ".git") + "\n"
            self.assertEqual(prof._main_checkout(), Path(d).parent / "main")


class IgnoredTest(unittest.TestCase):
    def test_git_ignores_machine_profiles_but_not_the_defaults(self):
        import subprocess

        def ignored(path: str) -> bool:
            return subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", "--no-index", path], check=False).returncode == 0

        self.assertTrue(ignored("machines/ANYHOST.yaml"))
        self.assertFalse(ignored("machines/_defaults.yaml"))
        self.assertTrue(ignored("litellm.db"))


if __name__ == "__main__":
    unittest.main()
