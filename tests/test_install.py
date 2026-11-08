"""Tests for the installer back end (stacklib/install.py) and the streaming model pull (stacklib/ollama.py).

Run with `uv run python -m unittest discover -s tests`.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import install, ollama  # noqa: E402

MACHINE = """# header comment
name: TESTBOX
# Windows paths: use single quotes so YAML keeps the backslashes literal.
model_store: 'D:\\ollama\\models'     # models live on D:
data_dir: ".run"

ollama_env:
  # per-machine additions
  OLLAMA_MODELS: 'D:\\ollama\\models'
"""


class CheckDir(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def test_relative_path_refused(self):
        self.assertFalse(install.check_dir("models", 1).ok)

    def test_empty_path_refused(self):
        self.assertEqual(install.check_dir("  ", 1).message, "Choose a folder.")

    @unittest.skipUnless(os.name == "nt", "drive letters are Windows only")
    def test_missing_drive_refused(self):
        free = next(f"{c}:\\" for c in "QRSTUVWXYZ" if not os.path.exists(f"{c}:\\"))
        chk = install.check_dir(free + "ollama\models", 1)
        self.assertFalse(chk.ok)
        self.assertIn("is not connected", chk.message)

    def test_folder_that_does_not_exist_yet_is_fine(self):
        chk = install.check_dir(str(self.tmp / "a" / "b"), 0.001)
        self.assertTrue(chk.ok, chk.message)

    def test_file_in_the_way_refused(self):
        (self.tmp / "f").write_text("x")
        self.assertFalse(install.check_dir(str(self.tmp / "f"), 0.001).ok)
        self.assertFalse(install.check_dir(str(self.tmp / "f" / "sub"), 0.001).ok)

    def test_not_enough_space_refused(self):
        chk = install.check_dir(str(self.tmp), 10**9)
        self.assertFalse(chk.ok)
        self.assertIn("free", chk.message)


class SavePaths(unittest.TestCase):
    def test_writes_both_keys_and_keeps_comments(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "TESTBOX.yaml"
            f.write_text(MACHINE, encoding="utf-8")
            with mock.patch.object(install.prof, "machine_file", return_value=f):
                install.save_paths({"name": "TESTBOX"}, "C:\\Users\\me\\.ollama\\models")
            text = f.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text)
        self.assertEqual(parsed["model_store"], "C:\\Users\\me\\.ollama\\models")
        self.assertEqual(parsed["ollama_env"]["OLLAMA_MODELS"], "C:\\Users\\me\\.ollama\\models")
        self.assertIn("# models live on D:", text)
        self.assertIn("# per-machine additions", text)
        self.assertNotIn("D:\\ollama", text)

    def test_adds_keys_that_are_missing(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "TESTBOX.yaml"
            f.write_text("name: TESTBOX\nmodels: {}\n", encoding="utf-8")
            with mock.patch.object(install.prof, "machine_file", return_value=f):
                install.save_paths({"name": "TESTBOX"}, "/srv/ollama")
            parsed = yaml.safe_load(f.read_text(encoding="utf-8"))
        self.assertEqual((parsed["model_store"], parsed["ollama_env"]["OLLAMA_MODELS"]), ("/srv/ollama", "/srv/ollama"))


class RunSteps(unittest.TestCase):
    def test_a_failed_step_is_recorded_and_the_rest_still_run(self):
        ran = []

        def ok(plan, profile, report):
            report("halfway", 0.5)
            ran.append("ok")
            return "fine"

        def boom(plan, profile, report):
            ran.append("boom")
            raise RuntimeError("disk on fire")

        def skip(plan, profile, report):
            ran.append("skip")
            raise install.Skip("not chosen")

        steps = (("a", "A", ok), ("b", "B", boom), ("c", "C", skip), ("d", "D", ok))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(install.prof, "resolve_profile", return_value={}), \
                mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            state_file = Path(d) / "state.json"
            result = install.run(install.Plan(model_store=d), state_file, steps)
            state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertFalse(result)
        self.assertEqual(ran, ["ok", "boom", "skip", "ok"])
        self.assertEqual([s["status"] for s in state["steps"]], ["done", "failed", "skipped", "done"])
        self.assertEqual(state["steps"][1]["detail"], "disk on fire")
        self.assertEqual(state["status"], "failed")

    def test_state_of_a_dead_worker_reads_as_interrupted(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "state.json"
            f.write_text(json.dumps({"status": "running", "pid": os.getpid(), "started": "not-this-process"}), encoding="utf-8")
            with mock.patch.object(install, "STATE_FILE", f):
                self.assertEqual(install.read_state()["status"], "interrupted")
                self.assertFalse(install.worker_running())


class _PullHandler(BaseHTTPRequestHandler):
    reply: tuple[int, list[dict]] = (200, [])

    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        code, events = self.reply
        self.send_response(code)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        if code != 200:
            self.wfile.write(json.dumps(events[0]).encode())
            return
        for ev in events:
            self.wfile.write((json.dumps(ev) + "\n").encode())

    def log_message(self, *a):
        pass


class PullStream(unittest.TestCase):
    def serve(self, code, events):
        handler = type("H", (_PullHandler,), {"reply": (code, events)})
        srv = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_port}"

    def test_progress_across_layers_then_success(self):
        base = self.serve(200, [
            {"status": "pulling manifest"},
            {"status": "pulling a", "digest": "a", "total": 100, "completed": 50},
            {"status": "pulling b", "digest": "b", "total": 300, "completed": 0},
            {"status": "pulling b", "digest": "b", "total": 300, "completed": 300},
            {"status": "success"},
        ])
        seen = []
        ollama.pull_stream(base, "m", lambda f, done, total: seen.append((f, done, total)))
        self.assertEqual(seen[-1], (350 / 400, 350, 400))

    def test_error_in_the_stream_raises(self):
        base = self.serve(200, [{"status": "pulling manifest"}, {"error": "pull model manifest: file does not exist"}])
        with self.assertRaisesRegex(RuntimeError, "file does not exist"):
            ollama.pull_stream(base, "m")

    def test_http_error_carries_ollamas_message(self):
        base = self.serve(400, [{"error": "mkdir D:\\ollama: The system cannot find the path specified."}])
        with self.assertRaisesRegex(RuntimeError, r"HTTP 400: mkdir D:\\ollama"):
            ollama.pull_stream(base, "m")


def _git(cwd, *args):
    import subprocess
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "init.defaultBranch=main",
                    *args], cwd=cwd, check=True, capture_output=True)


@unittest.skipUnless(install.which("git"), "git is not installed")
class CheckoutBehind(unittest.TestCase):
    """Real throwaway repositories: an origin, a clone of it, and commits the clone has not pulled yet."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.origin, self.clone = Path(tmp.name) / "origin", Path(tmp.name) / "clone"
        self.origin.mkdir()
        _git(self.origin, "init", "-q")
        self.commit("one")
        _git(tmp.name, "clone", "-q", str(self.origin), str(self.clone))
        patcher = mock.patch.object(install, "REPO", self.clone)
        patcher.start()
        self.addCleanup(patcher.stop)

    def commit(self, msg):
        _git(self.origin, "commit", "-q", "--allow-empty", "-m", msg)

    def test_up_to_date_says_nothing(self):
        self.assertEqual(install.checkout_behind(), "")

    def test_behind_after_fetch_names_the_count_and_the_fix(self):
        self.commit("two")
        self.commit("three")
        msg = install.checkout_behind()
        self.assertIn("2 commits behind origin/main", msg)
        self.assertIn("git pull", msg)
        self.assertNotIn("could not be reached", msg)

    def test_local_commits_ahead_do_not_warn(self):
        _git(self.clone, "commit", "-q", "--allow-empty", "-m", "mine")
        self.assertEqual(install.checkout_behind(), "")

    def test_unreachable_origin_falls_back_to_the_last_fetch(self):
        self.commit("two")
        _git(self.clone, "fetch", "-q")
        _git(self.clone, "remote", "set-url", "origin", str(self.origin.parent / "gone"))
        msg = install.checkout_behind()
        self.assertIn("1 commit behind", msg)
        self.assertIn("could not be reached", msg)

    def test_not_a_git_checkout_says_nothing(self):
        with tempfile.TemporaryDirectory() as plain, mock.patch.object(install, "REPO", Path(plain)):
            self.assertEqual(install.checkout_behind(), "")


if __name__ == "__main__":
    unittest.main()
