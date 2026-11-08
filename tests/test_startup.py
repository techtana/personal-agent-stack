"""Tests for the tray's start-up reporting: the launcher's log watch (stacklib/startup.py) and the failure message
shown under pythonw (scripts/tray.py).

Run with `uv run python -m unittest discover -s tests`.
"""
from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import tray  # noqa: E402
from stacklib import startup  # noqa: E402


class WaitForTray(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.log = Path(tmp.name) / "tray.log"
        self.log.write_text("[tray] ready pid 1\n", encoding="utf-8")  # an earlier run, before the launch
        self.offset = self.log.stat().st_size

    def _append_later(self, text: str, delay: float = 0.3) -> None:
        def write():
            with open(self.log, "a", encoding="utf-8") as f:
                f.write(text)

        timer = threading.Timer(delay, write)
        timer.start()
        self.addCleanup(timer.cancel)

    def test_ready_line_after_the_launch(self):
        self._append_later("[tray] 2026-11-01T10:00:00 starting pid 42\n[tray] ready pid 42\n")
        state, msg = startup.wait_for_tray(self.log, self.offset, timeout=5, alive=lambda: 42, poll=0.05)
        self.assertEqual((state, msg), ("ready", "running (pid 42)"))

    def test_failure_line_gives_the_reason(self):
        self._append_later("Traceback (most recent call last):\n[tray] start-up failed: FileNotFoundError: no machine profile at X.yaml\n")
        state, msg = startup.wait_for_tray(self.log, self.offset, timeout=5, alive=lambda: 42, poll=0.05)
        self.assertEqual(state, "failed")
        self.assertIn("FileNotFoundError: no machine profile at X.yaml", msg)
        self.assertIn(str(self.log), msg)

    def test_lines_from_an_earlier_run_do_not_count(self):
        state, msg = startup.wait_for_tray(self.log, self.offset, timeout=0.3, alive=lambda: None, poll=0.05)
        self.assertEqual(state, "failed")
        self.assertIn("did not start", msg)

    def test_a_tray_that_dies_silently_is_a_failure(self):
        alive = iter([42, 42, None, None])
        state, msg = startup.wait_for_tray(self.log, self.offset, timeout=5, alive=lambda: next(alive, None), poll=0.05)
        self.assertEqual(state, "failed")
        self.assertIn("exited during start-up", msg)

    def test_alive_but_silent_at_the_timeout(self):
        state, msg = startup.wait_for_tray(self.log, self.offset, timeout=0.3, alive=lambda: 42, poll=0.05)
        self.assertEqual(state, "running")
        self.assertIn("pid 42", msg)

    def test_another_instance(self):
        self._append_later("[tray] another tray instance is running; exiting\n")
        state, _ = startup.wait_for_tray(self.log, self.offset, timeout=5, alive=lambda: None, poll=0.05)
        self.assertEqual(state, "ready")


class ShowRequest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(startup, "SHOW_REQUEST", Path(tmp.name) / "run" / "tray.show")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_one_request_is_taken_once(self):
        self.assertFalse(startup.take_show_request())
        startup.request_show()
        self.assertTrue(startup.take_show_request())
        self.assertFalse(startup.take_show_request())


class MenuShortcut(unittest.TestCase):
    def test_written_with_show_and_start_at_login_refreshed(self):
        # Rewritten every time, so shortcuts made before PAS-Tray.exe start it (and carry the tray's icon).
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(startup, "IS_WINDOWS", True), \
                mock.patch.object(startup, "_menu_dir", return_value=Path(tmp)), \
                mock.patch.object(startup, "_autostart_file", return_value=Path(tmp) / "startup.lnk"), \
                mock.patch.object(startup, "_make_shortcut", side_effect=lambda p, show=False: p.touch()) as make:
            lnk = startup.ensure_menu_shortcut()
            self.assertEqual(lnk, Path(tmp) / startup.SHORTCUT_NAME)
            make.assert_called_once_with(lnk, show=True)  # start at login is off: only the menu entry
            (Path(tmp) / "startup.lnk").touch()
            make.reset_mock()
            startup.ensure_menu_shortcut()
            self.assertEqual(make.call_args_list, [mock.call(lnk, show=True), mock.call(Path(tmp) / "startup.lnk")])

    def test_nothing_outside_windows(self):
        with mock.patch.object(startup, "IS_WINDOWS", False), mock.patch.object(startup, "_make_shortcut") as make:
            self.assertIsNone(startup.ensure_menu_shortcut())
            make.assert_not_called()


class StartupFailureText(unittest.TestCase):
    def test_missing_machine_profile_says_what_to_run(self):
        exc = FileNotFoundError(r"no machine profile at C:\repo\machines\NOSUCH.yaml; run: uv run scripts/stack.py doctor --write-profile")
        text = tray.startup_failure_text(exc)
        self.assertIn(r"C:\repo\machines\NOSUCH.yaml does not exist", text)
        self.assertIn("uv run scripts/stack.py doctor --write-profile", text)
        self.assertIn(str(tray.LOG_FILE), text)

    def test_import_error_points_at_uv_sync(self):
        text = tray.startup_failure_text(ImportError("DLL load failed while importing _imaging: An Application Control policy has blocked this file."))
        self.assertIn("uv sync", text)
        self.assertIn("Smart App Control", text)

    def test_log_markers_match_the_launcher(self):
        self.assertEqual((tray.READY, tray.FAILED), (startup.TRAY_READY, startup.TRAY_FAILED))
        self.assertEqual(tray.LOG_FILE, startup.TRAY_LOG)


if __name__ == "__main__":
    unittest.main()
