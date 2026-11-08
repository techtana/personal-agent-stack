"""Tests for choosing features in the installer: the profile switches it writes (install.save_features), the plan it
starts (install.feature_plan), the space each folder needs, the recordings step, opening the window from the tray, and
the installer window's two pages (scripts/installer.py) built hidden.

Run with `uv run --with pytest python -m pytest -q tests/test_installer_features.py`.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))
from stacklib import features, install, whisper  # noqa: E402
from stacklib import profile as prof  # noqa: E402
from test_features import hw, make_profile  # noqa: E402

S = features.Status
MACHINE = """# header comment
name: TESTBOX
model_store: 'D:\\ollama\\models'     # models live on D:

services:
  comfyui: 'off'   # keep this comment

agent_access:
  allowed_roots: []
"""

_guards: list = []


def _refuse(*_a, **_k):
    raise AssertionError("a test reached a real installer action; mock it inside the test")


def setUpModule():
    # Nothing here may start setup, write the real machine profile, or change Claude Desktop's config.
    for target, name in ((install, "spawn_worker"), (install, "save_paths"), (prof, "write_profile"),
                         (whisper, "register_desktop"), (whisper, "unregister_desktop"), (whisper, "install")):
        g = mock.patch.object(target, name, _refuse)
        g.start()
        _guards.append(g)


def tearDownModule():
    for g in _guards:
        g.stop()


def statuses(**over) -> dict[str, features.Status]:
    """Everything required installed, every optional feature not installed, unless over says otherwise."""
    out = {f.id: S(True, True, "Installed") if f.required else S(False, False, "Not installed", level="off")
           for f in features.FEATURES}
    out.update(over)
    return out


class Temp(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)


class SaveFeatures(Temp):
    def setUp(self):
        super().setUp()
        self.file = self.tmp / "TESTBOX.yaml"
        self.file.write_text(MACHINE, encoding="utf-8")
        patcher = mock.patch.object(install.prof, "machine_file", return_value=self.file)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.profile = {"name": "TESTBOX", "services": {"open_webui": "native", "comfyui": "off", "dictation": "off"},
                        "observability": {"phoenix": True}, "media": {"hf_home": "E:\\hf"}}

    def saved(self) -> dict:
        return yaml.safe_load(self.file.read_text(encoding="utf-8"))

    def test_writes_only_what_changes_and_keeps_comments(self):
        install.save_features(self.profile, {"voice_typing"}, status=statuses())
        doc, text = self.saved(), self.file.read_text(encoding="utf-8")
        self.assertEqual(doc["services"], {"comfyui": "off", "open_webui": "off", "dictation": "native"})
        self.assertIs(doc["observability"]["phoenix"], False)
        self.assertNotIn("media", doc)   # no feature that needs the media folder
        self.assertIn("# keep this comment", text)
        self.assertIn("# models live on D:", text)

    def test_never_turns_off_an_installed_feature_that_is_on(self):
        install.save_features(self.profile, set(), status=statuses(chat=S(True, True, "Installed"),
                                                                    tracing=S(True, True, "Installed")))
        doc = self.saved()
        self.assertNotIn("open_webui", doc["services"])   # stays native: unchanged, so not written
        self.assertNotIn("observability", doc)

    def test_media_folder_for_images(self):
        install.save_features(self.profile, {"chat", "tracing", "images"}, "F:\\media", statuses())
        doc = self.saved()
        self.assertEqual(doc["services"]["comfyui"], "native")
        self.assertEqual(doc["media"]["root"], "F:\\media")
        self.assertEqual(doc["agent_access"]["allowed_roots"], ["F:\\media", "E:\\hf"])

    def test_media_folder_is_ignored_without_a_feature_that_needs_it(self):
        install.save_features(self.profile, {"chat", "tracing", "voice_typing"}, "F:\\media", statuses())
        self.assertNotIn("media", self.saved())

    def test_nothing_to_change(self):
        self.assertIsNone(install.save_features(self.profile, {"chat", "tracing"}, status=statuses()))
        self.assertEqual(self.file.read_text(encoding="utf-8"), MACHINE)

    def test_a_feature_whose_check_failed_keeps_its_switch(self):
        # `uv tool dir` failed: Open WebUI and Phoenix are unknown. Unticking them must not turn a working one off.
        unknown = S(False, True, features.NOT_CHECKED, "uv did not answer", "warn")
        self.assertIsNone(install.save_features(self.profile, set(), status=statuses(chat=unknown, tracing=unknown)))
        self.assertEqual(self.file.read_text(encoding="utf-8"), MACHINE)


class PlanAndSpace(Temp):
    def test_feature_plan(self):
        plan = install.feature_plan({"images", "openclaw"}, statuses(openclaw=S(True, False, "Not set up", level="warn")))
        self.assertEqual(plan, {"setup_media": True, "install_openclaw": False, "setup_openclaw": True,
                                "setup_recordings": False})
        plan = install.feature_plan({"recordings", "openclaw"}, statuses())
        self.assertEqual(plan, {"setup_media": False, "install_openclaw": True, "setup_openclaw": True,
                                "setup_recordings": True})
        self.assertLessEqual(set(plan), set(vars(install.Plan(model_store="x"))))   # every key is a Plan field

    def test_space_each_folder_needs(self):
        with mock.patch.object(features, "_whisper_cached", return_value=False):
            est = features.estimates(make_profile(self.tmp), hw())
        status = statuses(gateway=S(True, True, "Installed"))
        self.assertAlmostEqual(install.tools_need_gb({"chat", "tracing"}, est, status), 1.9 + 0.5)
        self.assertAlmostEqual(install.tools_need_gb({"chat"}, est, status, moving=True), 0.6 + 1.9)
        self.assertEqual(install.tools_need_gb(set(), est, status), 0.1)
        self.assertAlmostEqual(install.media_need_gb({"images", "recordings", "voice_typing"}, est, status),
                               16.8 + 2.4 + 0.3 + 1.6)
        self.assertAlmostEqual(install.media_need_gb({"images", "recordings"}, est,
                                                     statuses(images=S(True, True, "Installed"))), 2.4 + 1.6)
        self.assertTrue(install.needs_media({"recordings"}))
        self.assertFalse(install.needs_media({"voice_typing", "chat"}))
        # A new media folder gets everything again, installed or not, even what is only partly there in the old one.
        self.assertAlmostEqual(install.media_need_gb({"images"}, est, statuses(images=S(True, True, "Installed")),
                                                     moved=True), 16.8)
        partly = {**est, "images": features.Estimate(disk_gb=16.8, todo_gb=6.2)}   # ComfyUI there, a model missing
        model_missing = statuses(images=S(False, True, "Model missing", level="warn"))
        self.assertAlmostEqual(install.media_need_gb({"images"}, partly, model_missing), 6.2)
        self.assertAlmostEqual(install.media_need_gb({"images"}, partly, model_missing, moved=True), 16.8)
        self.assertTrue(install.media_moved({"media": {"root": "D:\\media"}}, "E:\\media"))
        self.assertFalse(install.media_moved({"media": {"root": "D:\\media"}}, "D:\\media"))
        self.assertFalse(install.media_moved({"media": {}}, "E:\\media"))   # no folder yet: nothing installed to move

    def test_space_the_models_folder_needs(self):
        p = make_profile(self.tmp / "models")
        with mock.patch.object(features, "_whisper_cached", return_value=False):
            est = features.estimates(p, hw())
        d = {"estimates": est, "models_gb": 7.9, "move_gb": 3.0}
        here = str(self.tmp / "models")
        self.assertEqual(install.store_need_gb(d, p, here, pull=True), 7.9)   # nothing pulled yet
        self.assertEqual(install.store_need_gb(d, p, here, pull=False), 0.1)
        for m in features.models_to_pull(p):
            path = features.manifest_path(here, m)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
        est = features.estimates(p, hw())
        d["estimates"] = est
        self.assertEqual(install.store_need_gb(d, p, here, pull=True), 0.1)    # all there already
        elsewhere = str(self.tmp / "other")
        self.assertEqual(install.store_need_gb(d, p, elsewhere, pull=True), 7.9)
        self.assertEqual(install.store_need_gb(d, p, "Z:\\models", pull=True, move_from=here), 7.9 + 3.0)


class StepRecordings(Temp):
    def setUp(self):
        super().setUp()
        self.media = self.tmp / "media"
        self.profile = make_profile(self.tmp, media=prof.resolve_media({}, {"root": str(self.media)}),
                                    agent_access={"allowed_roots": [str(self.media)]})
        self.repo = self.tmp / "repo"
        (self.repo / ".git").mkdir(parents=True)   # a main checkout: .git is a folder
        # desktop_entry stands for this PC's real Claude Desktop config, which must not decide a test.
        self.entry = mock.Mock(return_value=None)
        for target, name, value in ((install, "REPO", self.repo), (features, "desktop_entry", self.entry),
                                    (whisper, "register_desktop", mock.Mock(return_value="registered")),
                                    (whisper, "install", mock.Mock(return_value="installed faster-whisper"))):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_step(self, **plan) -> str:
        return install.step_recordings(install.Plan(model_store="x", **plan), self.profile, lambda *a: None)

    def install_env(self, server: bytes) -> Path:
        python = whisper.whisper_python(self.profile)
        python.parent.mkdir(parents=True)
        python.write_text("", encoding="utf-8")
        target = whisper.whisper_dir(self.profile) / "whisper_mcp.py"
        target.write_bytes(server)
        return target

    def test_not_chosen_or_no_media_folder(self):
        with self.assertRaisesRegex(install.Skip, "not chosen"):
            self.run_step()
        self.profile["media"] = {}
        with self.assertRaisesRegex(install.Skip, "media folder"):
            self.run_step(setup_recordings=True)

    def test_new_install_registers_in_claude_desktop(self):
        self.assertEqual(self.run_step(setup_recordings=True), "installed faster-whisper; registered")
        whisper.install.assert_called_once()
        whisper.register_desktop.assert_called_once_with(self.profile)

    def test_installed_but_not_in_claude_desktop_gets_the_current_server_and_an_entry(self):
        target = self.install_env(b"old server")
        self.assertEqual(self.run_step(setup_recordings=True), "updated the server; registered")
        self.assertEqual(target.read_bytes(), whisper.SERVER_SRC.read_bytes())
        self.assertEqual(self.run_step(setup_recordings=True), "already installed; registered")
        whisper.install.assert_not_called()

    def test_an_entry_already_in_claude_desktop_is_never_rewritten(self):
        self.entry.return_value = {"command": "python", "env": {"MY_OWN": "1"}}
        target = self.install_env(b"old server")
        with self.assertRaisesRegex(install.Skip, "already installed and in Claude Desktop"):
            self.run_step(setup_recordings=True)
        self.assertEqual(target.read_bytes(), b"old server")   # linked: not even the server file changes
        target.unlink()   # the entry is there, the files are not: install them, leave the entry
        self.assertIn("entry was left as it is", self.run_step(setup_recordings=True))
        whisper.install.assert_called_once()
        whisper.register_desktop.assert_not_called()

    def test_a_worktree_never_writes_claude_desktops_config(self):
        (self.repo / ".git").rmdir()
        (self.repo / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
        with self.assertRaisesRegex(install.Warn, "Not added to Claude Desktop: this folder is a git worktree"):
            self.run_step(setup_recordings=True)
        whisper.install.assert_called_once()   # the environment is shared, so it is installed all the same
        whisper.register_desktop.assert_not_called()


class LaunchWindow(unittest.TestCase):
    def test_opens_the_installer_in_its_own_process(self):
        with mock.patch.object(install.subprocess, "Popen", return_value=mock.Mock(pid=4321)) as popen:
            self.assertEqual(install.launch_window(), 4321)
        cmd, kwargs = popen.call_args.args[0], popen.call_args.kwargs
        self.assertEqual(Path(cmd[1]), REPO / "scripts" / "installer.py")
        self.assertEqual(kwargs["env"]["AGENT_STACK_HIDE_CONSOLE"], "1")
        self.assertEqual(Path(kwargs["cwd"]), REPO)
        if os.name == "nt":
            self.assertEqual(kwargs["creationflags"], install.services.WINDOWS_FLAGS)

    @unittest.skipUnless(os.name == "nt", "job breakaway is Windows only")
    def test_retries_inside_the_job_when_breakaway_is_refused(self):
        calls = []

        def popen(cmd, **kwargs):
            calls.append(kwargs["creationflags"])
            if len(calls) == 1:
                raise PermissionError("breakaway refused")
            return mock.Mock(pid=7)

        with mock.patch.object(install.subprocess, "Popen", side_effect=popen):
            self.assertEqual(install.launch_window(), 7)
        self.assertFalse(calls[1] & install.services.CREATE_BREAKAWAY_FROM_JOB)


def _tk():
    try:
        import tkinter as tk

        root = tk.Tk()
    except Exception:  # noqa: BLE001 - no Tk or no display
        return None
    root.withdraw()
    return root


class InstallerWindow(Temp):
    """The real window, never shown: page 1 (features), page 2 (folders), Install."""

    def setUp(self):
        super().setUp()
        self.root = _tk()
        if self.root is None:
            self.skipTest("Tk cannot open a window here")
        self.addCleanup(self.root.destroy)
        import tkinter as tk
        from tkinter import filedialog, ttk

        import installer
        self.profile = make_profile(self.tmp / "models")
        self.status = statuses(
            chat=S(True, True, "Installed"),                                   # locked
            tracing=S(True, False, "Installed, off", level="off"),             # off on purpose: stays unticked
            openclaw=S(True, False, "Bypasses the gateway", level="warn"),     # offered the fix: ticked
        )
        h = hw()
        with mock.patch.object(features, "_whisper_cached", return_value=False):
            est = features.estimates(self.profile, h)
        self.d = {"model_store": str(self.tmp / "models"), "model_note": "", "move_from": "", "move_gb": 0.0,
                  "tool_dir": str(self.tmp / "tools"), "tools_missing": [], "ollama_missing": False,
                  "openclaw_installed": True, "openclaw_state": "Bypasses the gateway",
                  "models": features.models_to_pull(self.profile), "models_gb": 7.9,
                  "media_root": str(self.tmp / "media"), "media_installed": False, "hardware": h,
                  "features": self.status, "estimates": est, "choice": features.initial_choice(self.status, h)}
        self.calls = {"save_paths": mock.Mock(), "save_features": mock.Mock(), "spawn_worker": mock.Mock(return_value=1)}
        patches = [
            mock.patch.object(install, "worker_running", return_value=False),
            mock.patch.object(install, "defaults", return_value=self.d),
            mock.patch.object(install, "checkout_behind", return_value=""),
            mock.patch.object(install, "check_dir", return_value=install.PathCheck(True, "fine", 100.0)),
            mock.patch.object(install, "read_state", return_value={"status": "running", "steps": []}),
            mock.patch.object(prof, "write_profile", return_value=None),
            mock.patch.object(prof, "resolve_profile", return_value=self.profile),
            *[mock.patch.object(install, name, m) for name, m in self.calls.items()],
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.app = installer.Installer(self.root, tk, ttk, filedialog)

    def summary(self) -> str:
        return " | ".join(w.cget("text") for w in self.app.summary_box.winfo_children() if len(w.cget("text")) > 2)

    def test_required_and_installed_features_cannot_be_unticked(self):
        boxes = self.app.feature_boxes
        for fid in ("models", "gateway", "chat"):
            self.assertTrue(boxes[fid].instate(["disabled"]), fid)
            self.assertTrue(self.app.feature_vars[fid].get(), fid)
        for fid in ("tracing", "images", "voice_typing", "recordings", "openclaw"):
            self.assertFalse(boxes[fid].instate(["disabled"]), fid)
        ticked = {fid for fid, v in self.app.feature_vars.items() if v.get()}
        self.assertEqual(ticked, {"models", "gateway", "chat", "images", "openclaw"})

    def test_the_summary_follows_the_ticks(self):
        self.assertIn("An image needs about 10.5 GB", self.summary())
        self.assertNotIn("voice typing 1.2", self.summary())
        self.app.feature_vars["voice_typing"].set(True)
        self.app.feature_vars["images"].set(False)
        self.app.update_summary()
        self.assertIn("voice typing 1.2", self.summary())
        self.assertNotIn("An image", self.summary())

    def test_the_detail_box_explains_a_row(self):
        self.app.show_detail("openclaw")
        text = self.app.detail.cget("text")
        self.assertIn("Bypasses the gateway", text)
        self.assertIn("Tick it to make the gateway its only model provider", text)
        self.app.show_detail("chat")
        self.assertIn("To turn it off, use Settings in the tray", self.app.detail.cget("text"))

    def test_media_folder_only_for_features_that_need_it_and_back_keeps_the_ticks(self):
        self.app.show_folders()
        self.assertIsNotNone(self.app.media_msg)   # images are ticked
        self.app.show_features()
        self.app.feature_vars["images"].set(False)
        self.app.feature_vars["voice_typing"].set(True)
        self.app.show_folders()
        self.assertIsNone(self.app.media_msg)
        self.app.show_features()
        self.assertTrue(self.app.feature_vars["voice_typing"].get())
        self.assertFalse(self.app.feature_vars["images"].get())

    def test_moving_models_is_offered_only_for_another_folder(self):
        self.d["move_from"], self.d["move_gb"] = self.d["model_store"], 7.8
        self.app.show_folders()
        self.assertFalse(self.app.move_box.winfo_ismapped() or self.app.move_box.grid_info())
        self.app.store.set(str(self.tmp / "elsewhere"))
        self.assertTrue(self.app.move_box.grid_info())

    def test_install_writes_the_choice_and_starts_the_plan(self):
        self.app.feature_vars["recordings"].set(True)
        self.app.show_folders()
        self.assertTrue(self.app.validate())
        self.app.on_install()
        _profile, chosen, media_root, status = self.calls["save_features"].call_args.args
        self.assertEqual(chosen, {"models", "gateway", "chat", "images", "recordings", "openclaw"})
        self.assertEqual(media_root, str(self.tmp / "media"))
        self.assertIs(status, self.status)
        plan = self.calls["spawn_worker"].call_args.args[0]
        self.assertEqual((plan.setup_media, plan.setup_recordings, plan.install_openclaw, plan.setup_openclaw),
                         (True, True, False, True))
        self.assertEqual(plan.media_root, str(self.tmp / "media"))
        self.assertEqual(self.app.heading.cget("text"), install.summary({"status": "running"}))


if __name__ == "__main__":
    unittest.main()
