"""Tests for scripts/stacklib/paths.py: the path guard of decision D-M6 (plan task T08)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import IS_WINDOWS, paths  # noqa: E402


def profile(roots, **media):
    return {"name": "TEST", "agent_access": {"allowed_roots": roots}, "media": media, "ollama_env": {}, "model_store": ""}


class Inside(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "media"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_root_itself_and_below(self):
        self.assertTrue(paths.inside(str(self.root), [str(self.root)]))
        self.assertTrue(paths.inside(str(self.root / "comfyui" / "models"), [str(self.root)]))

    def test_sibling_with_a_common_prefix_is_outside(self):
        self.assertFalse(paths.inside(str(self.root) + "-other", [str(self.root)]))

    def test_dot_dot_is_resolved(self):
        self.assertFalse(paths.inside(str(self.root / ".." / "elsewhere"), [str(self.root)]))
        self.assertTrue(paths.inside(str(self.root / "a" / ".." / "b"), [str(self.root)]))

    def test_relative_paths_are_refused(self):
        self.assertFalse(paths.inside("media/comfyui", [str(self.root)]))

    @unittest.skipUnless(IS_WINDOWS, "drive letters and case folding")
    def test_windows_case_and_drive_letters(self):
        self.assertTrue(paths.inside(r"d:\MEDIA\comfyui", [r"D:\media"]))
        self.assertFalse(paths.inside(r"E:\media\comfyui", [r"D:\media"]))

    def test_symlink_pointing_outside_is_judged_by_its_target(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        link = self.root / "link"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("creating symlinks needs Developer Mode or admin on Windows")
        self.assertFalse(paths.inside(str(link / "file"), [str(self.root)]))


class Check(unittest.TestCase):
    def test_empty_list_refuses_every_media_path(self):
        errors, _ = paths.check(profile([], root=r"D:\media"))
        self.assertEqual(len(errors), 1)
        self.assertIn("empty", errors[0])

    def test_no_media_paths_and_no_roots_is_fine(self):
        self.assertEqual(paths.check(profile([])), ([], []))

    def test_path_outside_the_list_fails(self):
        base = tempfile.gettempdir()
        errors, _ = paths.check(profile([os.path.join(base, "media")], root=os.path.join(base, "media"),
                                        hf_home=os.path.join(base, "elsewhere")))
        self.assertEqual(len(errors), 1)
        self.assertIn("media.hf_home", errors[0])

    def test_old_model_store_outside_is_only_a_warning(self):
        base = tempfile.gettempdir()
        p = profile([os.path.join(base, "media")], root=os.path.join(base, "media"))
        p["ollama_env"] = {"OLLAMA_MODELS": os.path.join(base, "ollama")}
        errors, warnings = paths.check(p)
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)

    def test_require_raises(self):
        base = tempfile.gettempdir()
        with self.assertRaises(PermissionError):
            paths.require(profile([]), os.path.join(base, "x"), "test")
        with self.assertRaises(PermissionError):
            paths.require(profile([os.path.join(base, "a")]), os.path.join(base, "b"), "test")
        self.assertEqual(paths.require(profile([base]), os.path.join(base, "b"), "test"), os.path.join(base, "b"))


if __name__ == "__main__":
    unittest.main()
