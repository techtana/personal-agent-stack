"""Tests for installing the stack as its own app (stacklib/deploy.py): after an install, nothing the app runs may read
or write the source checkout.

Run with `uv run --with pytest python -m pytest tests/test_deploy.py -q`.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import REPO, deploy, install  # noqa: E402

PROFILE = """# machine profile
name: TESTBOX
data_dir: '{data_dir}'
models: {{}}
"""


def _write(p: Path, text: str = "x") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _fake_source(root: Path, data_dir: str = ".run") -> Path:
    """A source folder that is not a git checkout (deploy falls back to walking it), with state and secrets."""
    for rel in ("scripts/stack.py", "scripts/stacklib/__init__.py", "agents/docs.yaml", "machines/_defaults.yaml",
                "machines/README.md", "memory/lessons.md", "pyproject.toml", "start.cmd"):
        _write(root / rel, f"source {rel}")
    _write(root / "tests" / "test_x.py")
    _write(root / ".env", "LITELLM_MASTER_KEY=sk-test\n")
    _write(root / ".personal-terms", "secret-word\n")
    _write(root / "machines" / "TESTBOX.yaml", PROFILE.format(data_dir=data_dir))
    _write(root / ".run" / "pids" / "tray.pid", "1")
    _write(root / ".run" / "logs" / "tray.log", "log")
    _write(root / ".run" / "install" / "state.json", "{}")
    _write(root / ".run" / "dictation" / "refine-log.jsonl", "{}\n")
    _write(root / "traces" / "litellm" / "2026-11-08.jsonl", "{}\n")
    _write(root / "orchestrator" / "data" / "jobs.sqlite", "")
    (root / "orchestrator" / "data" / "jobs.sqlite").unlink()
    _write(root / "scripts" / "__pycache__" / "stack.cpython-314.pyc")
    db = root / ".run" / "open-webui" / "webui.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE file (id TEXT, path TEXT, meta JSON)")
    upload = root / ".run" / "open-webui" / "uploads" / "a.png"
    _write(upload, "png")
    con.execute("INSERT INTO file VALUES ('1', ?, ?)", (str(upload), json.dumps({"path": str(upload)})))
    con.commit()
    con.close()
    return root


class SourceFiles(unittest.TestCase):
    def test_walk_skips_state_secrets_tests_and_profiles(self):
        with tempfile.TemporaryDirectory() as t:
            src = _fake_source(Path(t) / "src")
            files = deploy.source_files(src)
        self.assertIn("scripts/stack.py", files)
        self.assertIn("machines/_defaults.yaml", files)
        self.assertIn("machines/README.md", files)
        for bad in (".env", ".personal-terms", "machines/TESTBOX.yaml", "tests/test_x.py", ".run/pids/tray.pid",
                    "traces/litellm/2026-11-08.jsonl", "scripts/__pycache__/stack.cpython-314.pyc",
                    ".run/open-webui/webui.db"):
            self.assertNotIn(bad, files)

    def test_real_checkout_lists_tracked_app_files_only(self):
        files = deploy.source_files(REPO)
        self.assertIn("scripts/stack.py", files)
        self.assertIn("machines/_defaults.yaml", files)
        self.assertFalse([f for f in files if f.startswith(("tests/", ".run/", "traces/")) or f == ".env"])


class CopyApp(unittest.TestCase):
    def test_copy_keeps_app_memory_and_removes_files_the_source_dropped(self):
        with tempfile.TemporaryDirectory() as t:
            src, dst = _fake_source(Path(t) / "src"), Path(t) / "app"
            first = deploy.copy_app(src, dst)
            self.assertEqual(first["copied"], len(deploy.source_files(src)))
            self.assertFalse((dst / ".env").exists())
            self.assertFalse((dst / "tests").exists())
            _write(dst / "memory" / "lessons.md", "lesson the app recorded")
            (src / "agents" / "docs.yaml").unlink()
            _write(src / "scripts" / "stack.py", "newer")
            second = deploy.copy_app(src, dst)
            self.assertEqual((dst / "memory" / "lessons.md").read_text(encoding="utf-8"), "lesson the app recorded")
            self.assertFalse((dst / "agents" / "docs.yaml").exists())
            self.assertEqual((dst / "scripts" / "stack.py").read_text(encoding="utf-8"), "newer")
            self.assertEqual(second["removed"], 1)
            self.assertEqual(second["kept"], 1)


class MigrateData(unittest.TestCase):
    def test_brings_over_settings_and_data_but_not_run_state(self):
        with tempfile.TemporaryDirectory() as t:
            src, dst = _fake_source(Path(t) / "src"), Path(t) / "app"
            deploy.copy_app(src, dst)
            deploy.migrate_data(src, dst, "TESTBOX", report=lambda *a: None)
            self.assertEqual((dst / ".env").read_text(encoding="utf-8"), "LITELLM_MASTER_KEY=sk-test\n")
            self.assertTrue((dst / "machines" / "TESTBOX.yaml").exists())
            self.assertTrue((dst / ".run" / "dictation" / "refine-log.jsonl").exists())
            self.assertTrue((dst / ".run" / "open-webui" / "uploads" / "a.png").exists())
            self.assertTrue((dst / "traces" / "litellm" / "2026-11-08.jsonl").exists())
            for gone in ("pids", "logs", "install"):
                self.assertFalse((dst / ".run" / gone).exists(), gone)

    def test_never_overwrites_the_apps_own_data(self):
        with tempfile.TemporaryDirectory() as t:
            src, dst = _fake_source(Path(t) / "src"), Path(t) / "app"
            _write(dst / ".env", "LITELLM_MASTER_KEY=sk-app\n")
            _write(dst / "machines" / "TESTBOX.yaml", "name: TESTBOX\n")
            deploy.migrate_data(src, dst, "TESTBOX", report=lambda *a: None)
            self.assertEqual((dst / ".env").read_text(encoding="utf-8"), "LITELLM_MASTER_KEY=sk-app\n")
            self.assertEqual((dst / "machines" / "TESTBOX.yaml").read_text(encoding="utf-8"), "name: TESTBOX\n")

    def test_absolute_data_dir_inside_the_source_becomes_relative(self):
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            _fake_source(src, data_dir=str(src / ".run"))
            dst = Path(t) / "app"
            deploy.migrate_data(src, dst, "TESTBOX", report=lambda *a: None)
            text = (dst / "machines" / "TESTBOX.yaml").read_text(encoding="utf-8")
            self.assertIn("data_dir: '.run'", text)
            self.assertNotIn(str(src), text)
            self.assertTrue((dst / ".run" / "open-webui" / "webui.db").exists())

    def test_copied_databases_point_into_the_app(self):
        with tempfile.TemporaryDirectory() as t:
            src, dst = _fake_source(Path(t) / "src"), Path(t) / "app"
            deploy.migrate_data(src, dst, "TESTBOX", report=lambda *a: None)
            con = sqlite3.connect(str(dst / ".run" / "open-webui" / "webui.db"))
            path, meta = con.execute("SELECT path, meta FROM file").fetchone()
            con.close()
            self.assertEqual(Path(path), dst / ".run" / "open-webui" / "uploads" / "a.png")
            self.assertEqual(Path(json.loads(meta)["path"]), dst / ".run" / "open-webui" / "uploads" / "a.png")
            # the checkout's own database is left as it was
            con = sqlite3.connect(str(src / ".run" / "open-webui" / "webui.db"))
            self.assertTrue(con.execute("SELECT path FROM file").fetchone()[0].startswith(str(src)))
            con.close()

    def test_prefix_match_stops_at_a_separator(self):
        with tempfile.TemporaryDirectory() as t:
            db = Path(t) / "x.db"
            con = sqlite3.connect(str(db))
            con.execute("CREATE TABLE f (p TEXT)")
            con.execute("INSERT INTO f VALUES (?)", (str(Path(t) / "src-other" / "a"),))
            con.commit()
            con.close()
            self.assertEqual(deploy.rebase_sqlite(db, Path(t) / "src", Path(t) / "app"), 0)


class Deploy(unittest.TestCase):
    def test_refuses_targets_that_overlap_the_source(self):
        with tempfile.TemporaryDirectory() as t:
            src = _fake_source(Path(t) / "src")
            for bad in (src, src / "app"):
                with self.assertRaises(ValueError):
                    deploy.check_target(src, bad)
            _write(Path(t) / "other" / "file.txt")
            with self.assertRaises(ValueError):
                deploy.check_target(src, Path(t) / "other")
            with self.assertRaises(ValueError):
                deploy.check_target(src / "scripts", src.parent)

    def test_leaves_no_path_back_to_the_source(self):
        with tempfile.TemporaryDirectory() as t:
            src = _fake_source(Path(t) / "src")
            app = deploy.deploy(src, Path(t) / "app", machine="TESTBOX", behind="3 commits behind", venv=False,
                                stop=False, report=lambda *a: None)
            self.assertTrue(deploy.is_app(app))
            self.assertFalse(deploy.is_app(src))
            self.assertEqual(deploy.read_marker(app)["behind"], "3 commits behind")
            root = str(src.resolve())
            needles = {root, root.replace("\\", "/"), root.replace("\\", "\\\\")}
            for f in (p for p in app.rglob("*") if p.is_file()):
                if f.suffix in (".db", ".sqlite"):
                    con = sqlite3.connect(str(f))
                    blob = "\n".join(con.iterdump())
                    con.close()
                else:
                    blob = f.read_bytes().decode("utf-8", "replace")
                for n in needles:
                    self.assertNotIn(n, blob, f"{f} names the source folder")

    def test_upgrade_keeps_data_and_installed_since(self):
        with tempfile.TemporaryDirectory() as t:
            src = _fake_source(Path(t) / "src")
            kw = dict(machine="TESTBOX", venv=False, stop=False, report=lambda *a: None)
            app = deploy.deploy(src, Path(t) / "app", **kw)
            since = deploy.read_marker(app)["first_installed_at"]
            _write(app / ".env", "LITELLM_MASTER_KEY=sk-app\n")
            _write(src / ".env", "LITELLM_MASTER_KEY=sk-newer-in-source\n")
            deploy.deploy(src, app, **kw)
            self.assertEqual((app / ".env").read_text(encoding="utf-8"), "LITELLM_MASTER_KEY=sk-app\n")
            self.assertEqual(deploy.read_marker(app)["first_installed_at"], since)

    def test_installed_copy_of_this_checkout_keeps_every_path_inside_itself(self):
        """Copy the real code, import it from the copy, and check where it would write."""
        with tempfile.TemporaryDirectory() as t:
            app = Path(t) / "app"
            deploy.copy_app(REPO, app)
            (app / deploy.MARKER).write_text("{}", encoding="utf-8")
            code = (
                "import json, sys; sys.path.insert(0, sys.argv[1]);"
                "import stacklib, stacklib.startup as st, stacklib.install as ins, stacklib.usage_log as ul;"
                "import stacklib.profile as pr, stacklib.procname as pn, stacklib.deploy as dp;"
                "print(json.dumps([str(p) for p in (stacklib.REPO, stacklib.ENV_FILE, stacklib.TRACES_DIR,"
                " stacklib.LITELLM_DIR, st.PIDFILE, st.TRAY_LOG, st.TRAY_SCRIPT, st.tray_python(), ins.STATE_FILE,"
                " ins.LOG_FILE, ul.default_dir(), pr.machine_file('TESTBOX'), pn.ICON_FILE)] + [dp.is_app()]))"
            )
            out = subprocess.run([sys.executable, "-c", code, str(app / "scripts")], capture_output=True, text=True,
                                 cwd=t, env={**os.environ, "AGENT_STACK_MACHINE": "TESTBOX"}, check=True).stdout
            *paths, is_app = json.loads(out)
            self.assertTrue(is_app)
            for p in paths:
                self.assertTrue(Path(p).resolve().is_relative_to(app.resolve()), p)


class LinksStep(unittest.TestCase):
    """The step that points start-up entries at the installed app writes nothing into a closed-source app's config."""

    def test_claude_desktops_config_is_left_alone(self):
        from stacklib import tasks, whisper

        with tempfile.TemporaryDirectory() as t:
            cfg = Path(t) / "claude_desktop_config.json"
            before = json.dumps({"mcpServers": {whisper.SERVER_NAME: {"command": "repo-python"}}})
            cfg.write_text(before, encoding="utf-8")
            with mock.patch.object(whisper, "desktop_config_path", return_value=cfg), \
                    mock.patch.object(tasks, "registered", return_value=set()), \
                    mock.patch.object(deploy, "is_app", return_value=True):
                detail = install.step_links(None, {}, lambda *a: None)
            self.assertEqual(cfg.read_text(encoding="utf-8"), before)
        self.assertEqual(detail, "nothing outside the app folder to update")


class CheckoutBehind(unittest.TestCase):
    def test_installed_app_reports_what_was_recorded_at_install(self):
        with mock.patch.object(deploy, "is_app", return_value=True), \
                mock.patch.object(deploy, "read_marker", return_value={"behind": "2 commits behind origin/main"}):
            self.assertEqual(install.checkout_behind(), "2 commits behind origin/main")


if __name__ == "__main__":
    unittest.main()
