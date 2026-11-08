"""Removing features and models (stacklib/uninstall.py), the worker plans that run it (stacklib/install.py), the
Storage card's scan (stacklib/storage.py) and the Services card's process rows (stacklib/modules.py).

Nothing here touches this PC's real folders, Ollama, Claude Desktop or services: every folder is a temporary one and
every outside call is patched.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from stacklib import catalog, features, install, modules, storage, uninstall  # noqa: E402

S = features.Status


def write(path: Path, size: int = 1000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


class Temp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.media = self.tmp / "media"
        self.data = REPO / ".run"
        self.profile = {
            "name": "TESTBOX", "data_dir": self.data,
            "ports": {"ollama": 11434, "dictation": 8790, "litellm": 4000},
            "models": {"primary": "qwen3.5:9b", "small": "qwen3.5:9b", "embed": "nomic-embed-text",
                       "fim": "qwen2.5-coder:1.5b-base"},
            "catalog": catalog.models(),
            "media": {"root": str(self.media), "comfyui_dir": str(self.media / "comfyui"),
                      "models_dir": str(self.media / "comfyui" / "models"), "output_dir": str(self.media / "outputs"),
                      "input_dir": str(self.media / "inputs"), "whisper_dir": str(self.media / "whisper"),
                      "hf_home": str(self.tmp / "hf"), "uv_cache": str(self.media / ".uv-cache")},
            "dictation": {"model": "large-v3-turbo", "cpu_model": "small"},
            "read_aloud": {"enabled": True},
            "services": {"dictation": "native"},
            "agent_access": {"allowed_roots": [str(self.media)]},
        }

    def tearDown(self):
        self._tmp.cleanup()


class Guard(Temp):
    def test_refuses_what_is_not_a_features_own_folder(self):
        g = lambda p, media=False: uninstall._guard(Path(p), self.profile, media)  # noqa: E731
        for bad in (Path(Path.home().anchor), Path.home(), Path.home().parent, REPO, REPO.parent, REPO / "scripts",
                    self.data):
            with self.subTest(path=bad), self.assertRaises(PermissionError):
                g(bad)
        with self.assertRaises(PermissionError):   # a media folder outside the allowed roots
            g(self.tmp / "elsewhere" / "comfyui", media=True)
        g(self.media / "comfyui", media=True)      # the feature's own folders pass
        with self.assertRaises(PermissionError):   # never an allowed root itself
            g(self.media, media=True)
        g(self.data / "dictation" / ".venv")       # voice typing's environment without a media folder

    def test_hugging_face_deletes_stay_in_the_hub(self):
        hub = self.tmp / "hf" / "hub"
        uninstall._hf_guard(hub / "models--Systran--faster-whisper-small", self.profile)
        for bad in (hub, self.tmp / "hf" / "models--x--y", hub / "datasets--x--y"):
            with self.subTest(path=bad), self.assertRaises(PermissionError):
                uninstall._hf_guard(bad, self.profile)

    def test_delete_tree_reports_the_size_and_tolerates_a_missing_folder(self):
        folder = self.media / "comfyui"
        write(folder / "a.bin", 1500)
        write(folder / "sub" / "b.bin", 500)
        self.assertEqual(uninstall.delete_tree(folder, self.profile, True), 2000)
        self.assertFalse(folder.exists())
        self.assertEqual(uninstall.delete_tree(folder, self.profile, True), 0)

    def test_short_text_hides_the_home_folder_anywhere_in_a_sentence(self):
        home = str(Path.home())
        self.assertEqual(uninstall.short_text(f"LiteLLM in {home}\\uv\\tools; and {home.upper()}\\x"),
                         "LiteLLM in ~\\uv\\tools; and ~\\x")
        self.assertEqual(uninstall.short_path(Path.home() / "a"), "~" + str(Path.home() / "a")[len(home):])
        self.assertEqual(uninstall.short_path("D:/models"), "D:/models")


class Plans(Temp):
    def status(self, **over):
        st = {f.id: S(True, True, "Installed") for f in features.FEATURES}
        st.update(over)
        return st

    def test_required_features_cannot_be_removed(self):
        for fid in ("models", "gateway"):
            self.assertIn("required", uninstall.plan(self.profile, fid, self.status()).blocked)

    def test_open_webui_keeps_the_chats(self):
        tools = self.tmp / "tools"
        write(tools / "open-webui" / "pyvenv.cfg", 2_000_000)
        with mock.patch.object(uninstall, "_tool_dir", return_value=tools):
            r = uninstall.plan(self.profile, "chat", self.status())
        self.assertEqual(r.blocked, "")
        self.assertAlmostEqual(r.size_gb, 0.002, places=4)
        self.assertIn("open-webui", r.text())
        self.assertTrue(any("chats" in k for k in r.keeps))

    def test_voice_typing_takes_read_aloud_and_keeps_shared_whisper_models(self):
        hub = self.tmp / "hf" / "hub"
        write(hub / "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo" / "blobs" / "a", 10)
        write(hub / "models--Systran--faster-whisper-small" / "blobs" / "a", 10)
        write(hub / "models--onnx-community--Kokoro-82M-v1.0-ONNX" / "blobs" / "a", 10)
        self.profile["media"]["whisper_model"] = "large-v3-turbo"
        with mock.patch.object(uninstall.features, "desktop_entry", return_value=None):
            shared = uninstall.plan(self.profile, "voice_typing", self.status())
            alone = uninstall.plan(self.profile, "voice_typing",
                                   self.status(recordings=S(False, False, "Not installed", level="off")))
        self.assertEqual(shared.also, ["read_aloud"])
        whisper = lambda r: sorted(i.what for i in r.deletes if i.what.startswith("Whisper"))  # noqa: E731
        self.assertEqual(whisper(shared), [])   # recordings still uses them
        self.assertEqual(whisper(alone), ["Whisper model large-v3-turbo", "Whisper model small"])
        self.assertTrue(any(i.what.startswith("Kokoro") for i in shared.deletes))

    def test_recordings_wait_for_claude_desktop_to_quit(self):
        write(self.media / "whisper" / "whisper_mcp.py")
        with mock.patch.object(uninstall, "running_from", return_value=[4242]), \
                mock.patch.object(uninstall.features, "desktop_entry", return_value={"command": "x"}):
            r = uninstall.plan(self.profile, "recordings", self.status())
        self.assertIn("Quit Claude Desktop", r.blocked)

    def test_remove_voice_typing_end_to_end(self):
        venv = self.media / "dictation" / ".venv"
        write(venv / "Scripts" / "python.exe")
        write(venv / "pyvenv.cfg")
        kokoro = write(self.tmp / "hf" / "hub" / "models--onnx-community--Kokoro-82M-v1.0-ONNX" / "x").parent
        status = self.status(recordings=S(True, True, "Linked"))
        with mock.patch.object(uninstall.features, "statuses", return_value=status), \
                mock.patch.object(uninstall.features, "desktop_entry", return_value=None), \
                mock.patch("stacklib.settings.save") as save, mock.patch("stacklib.settings.apply") as apply, \
                mock.patch("stacklib.settings.current_values", return_value={"read_aloud.enabled": True,
                                                                             "services.dictation": True}), \
                mock.patch("stacklib.profile.resolve_profile", return_value=self.profile), \
                mock.patch.object(uninstall, "_stop") as stop, \
                mock.patch.object(uninstall, "_reset_openwebui_stt", return_value=True):
            note = uninstall.remove(self.profile, "voice_typing")
        save.assert_called_once()          # read aloud is only written off: its app stops for good
        apply.assert_called_once()         # voice typing goes off the way Settings does it
        stop.assert_called_with(self.profile, ["dictation"])
        self.assertFalse(venv.exists())
        self.assertFalse(kokoro.exists())
        self.assertIn("read aloud", note)
        self.assertIn("own Whisper", note)

    def _removing(self, fid: str, status=None, **extra):
        """remove(fid) with Settings, services and outside programs stubbed; returns (note, stubs)."""
        stubs = {"apply": mock.Mock(), "stop": mock.Mock(), "run": mock.Mock(return_value=SimpleNamespace(
            returncode=0, stdout="", stderr="")), "provision": mock.Mock(return_value=["image_generation.enable"])}
        with mock.patch.object(uninstall.features, "statuses", return_value=status or self.status()), \
                mock.patch.object(uninstall.features, "desktop_entry", return_value=None), \
                mock.patch("stacklib.settings.apply", stubs["apply"]), \
                mock.patch("stacklib.settings.current_values", return_value={"services.open_webui": True,
                                                                             "services.comfyui": True}), \
                mock.patch("stacklib.profile.resolve_profile", return_value=self.profile), \
                mock.patch.object(uninstall, "_stop", stubs["stop"]), mock.patch.object(uninstall, "_run", stubs["run"]), \
                mock.patch("stacklib.media.provision_openwebui", stubs["provision"]), \
                mock.patch.object(uninstall, "which", return_value="uv"), \
                mock.patch("stacklib.services._uv_tool_dir_cache", []):
            for target, value in extra.items():
                setattr(uninstall, target, value)
            return uninstall.remove(self.profile, fid), stubs

    def test_remove_open_webui_uninstalls_the_tool_and_keeps_the_data(self):
        tools = self.tmp / "tools"
        env = write(tools / "open-webui" / "pyvenv.cfg", 3_000_000).parent
        data = write(self.tmp / "data" / "open-webui" / "webui.db").parent
        with mock.patch.object(uninstall, "_tool_dir", return_value=tools):
            note, stubs = self._removing("chat")
        stubs["apply"].assert_called_once()
        self.assertEqual(stubs["apply"].call_args.args[1], {"services.open_webui": False})
        stubs["stop"].assert_called_with(self.profile, ["open_webui"])
        self.assertEqual(stubs["run"].call_args.args[0][1:], ["tool", "uninstall", "open-webui"])
        self.assertIn("uninstalled open-webui", note)
        self.assertTrue(env.exists())   # the stubbed uv deleted nothing; the real one removes the environment
        self.assertTrue(data.exists())

    def test_remove_images_deletes_comfyui_and_keeps_the_pictures(self):
        comfy = write(self.media / "comfyui" / "models" / "vae" / "ae.safetensors").parent.parent.parent
        write(self.media / "comfyui" / "main.py")
        made = write(self.media / "outputs" / "cat.png")
        note, stubs = self._removing("images")
        self.assertFalse(comfy.exists())
        self.assertTrue(made.exists())
        stubs["stop"].assert_called_with(self.profile, ["comfyui"])
        self.assertEqual(stubs["provision"].call_args.args[1], {"image_generation.enable": False})
        self.assertIn("removed ComfyUI", note)

    def test_remove_refuses_while_blocked(self):
        with mock.patch.object(uninstall.features, "statuses", return_value={}), self.assertRaises(RuntimeError):
            uninstall.remove(self.profile, "gateway")


class Models(Temp):
    def test_rows_list_the_catalog_and_any_other_model(self):
        tags = {"models": [{"name": "qwen3.5:9b", "size": 6_600_000_000},
                           {"name": "nomic-embed-text:latest", "size": 274_000_000},
                           {"name": "llama9:7b", "size": 4_000_000_000}]}
        with mock.patch("stacklib.ollama.api", return_value=tags):
            rows = {r.name: r for r in uninstall.model_rows(self.profile)}
        self.assertTrue(rows["qwen3.5:9b"].downloaded)
        self.assertEqual(rows["qwen3.5:9b"].use, "chat, small tier")
        self.assertTrue(rows["nomic-embed-text"].downloaded)
        self.assertFalse(rows["gpt-oss:20b"].downloaded)
        self.assertEqual(rows["gpt-oss:20b"].role, "reviewer")
        self.assertFalse(rows["llama9:7b"].in_catalog)
        self.assertAlmostEqual(rows["llama9:7b"].size_gb, 4.0)

    def test_a_model_in_use_is_not_deleted(self):
        with mock.patch("urllib.request.urlopen") as urlopen:
            with self.assertRaises(RuntimeError):
                uninstall.remove_model(self.profile, "qwen3.5:9b")
            urlopen.assert_not_called()
            urlopen.return_value.__enter__.return_value = None
            self.assertEqual(uninstall.remove_model(self.profile, "gpt-oss:20b"), "deleted gpt-oss:20b")
            req = urlopen.call_args.args[0]
        self.assertEqual((req.get_method(), json.loads(req.data)["model"]), ("DELETE", "gpt-oss:20b"))


class WorkerPlans(Temp):
    def test_removals_come_first_and_read_aloud_goes_with_voice_typing(self):
        plan = install.Plan(model_store="x", remove=["read_aloud", "chat", "voice_typing"], remove_models=["a:1"], only=[])
        ids = [sid for sid, _t, _f in install.plan_steps(plan)]
        self.assertEqual(ids, ["remove_chat", "remove_voice_typing", "remove_models"])
        plan = install.Plan(model_store="x", remove=["read_aloud"], only=["build"], pull_models=["b:2"])
        self.assertEqual([sid for sid, _t, _f in install.plan_steps(plan)], ["remove_read_aloud", "build", "pull_more"])
        self.assertEqual(len(install.plan_steps(install.Plan(model_store="x"))), len(install.STEPS))

    def test_the_tray_install_runs_only_that_features_steps(self):
        status = {f.id: S(f.required, f.required, "Installed" if f.required else "Not installed", level="ok")
                  for f in features.FEATURES}
        with mock.patch.object(install, "save_features") as save, \
                mock.patch.object(install, "worker_running", return_value=False), \
                mock.patch.object(install, "spawn_worker", return_value=7) as spawn:
            self.assertEqual(install.start_feature(self.profile, "read_aloud", status), 7)
        plan = spawn.call_args.args[0]
        self.assertEqual(plan.only, ["secrets", "dictation", "read_aloud"])   # in STEPS order
        self.assertEqual(plan.targets, ["read_aloud", "voice_typing"])
        self.assertFalse(plan.start_stack or plan.check_disks or plan.restart_ollama)
        self.assertIn("voice_typing", save.call_args.args[1])

    def test_recordings_are_no_longer_set_up(self):
        with mock.patch.object(install, "spawn_worker") as spawn, self.assertRaisesRegex(ValueError, "no longer offered"):
            install.start_feature(self.profile, "recordings", {})
        spawn.assert_not_called()
        self.assertNotIn("recordings", [sid for sid, _t, _f in install.STEPS])
        self.assertFalse(features.locked("recordings", {"recordings": S(True, True, "Linked")}))
        self.assertFalse(features.initial_choice({"recordings": S(True, True, "Linked")}, features.Hardware())["recordings"])

    def test_a_tray_install_waits_for_a_running_setup(self):
        with mock.patch.object(install, "worker_running", return_value=True), \
                mock.patch.object(install, "save_features") as save, self.assertRaises(RuntimeError):
            install.start_feature(self.profile, "chat", {})
        save.assert_not_called()   # the profile is not touched when nothing can run

    def test_a_feature_that_needs_a_media_folder_goes_to_the_installer(self):
        self.profile["media"] = {}
        with mock.patch.object(install, "spawn_worker") as spawn, self.assertRaises(ValueError):
            install.start_feature(self.profile, "images", {})
        spawn.assert_not_called()

    def test_removal_plans_name_their_rows(self):
        with mock.patch.object(install, "spawn_worker", return_value=1) as spawn:
            install.start_removal(self.profile, ["chat"], models=["gpt-oss:20b"])
        plan = spawn.call_args.args[0]
        self.assertEqual((plan.remove, plan.remove_models, plan.targets, plan.only),
                         (["chat"], ["gpt-oss:20b"], ["chat", "models"], []))

    def test_an_older_plan_file_still_loads(self):
        p = self.tmp / "plan.json"
        p.write_text(json.dumps({"model_store": "x", "some_future_field": 1}), encoding="utf-8")
        with mock.patch.object(install, "run", return_value=True) as run:
            install.run_worker(p)
        self.assertEqual(run.call_args.args[0].model_store, "x")


class Storage(Temp):
    def test_scan_groups_models_programs_and_data(self):
        write(self.media / "comfyui" / "models" / "vae" / "ae.safetensors", 3_000_000)
        write(self.media / "comfyui" / "main.py", 2_000_000)
        write(self.media / "outputs" / "a.png", 500)
        write(self.tmp / "hf" / "hub" / "models--someone--thing" / "blobs" / "x", 5_000_000)
        write(self.tmp / "hf" / "hub" / "models--Systran--faster-whisper-small" / "blobs" / "x", 2_000_000)
        rows = [uninstall.ModelRow("qwen3.5:9b", 6.6, True, "chat", True),
                uninstall.ModelRow("gpt-oss:20b", 13.0, False, "", True)]
        status = {"voice_typing": S(True, True, "Installed")}
        with mock.patch.object(uninstall, "model_rows", return_value=rows), \
                mock.patch("stacklib.services._uv_tool_dir", return_value=None), \
                mock.patch.object(storage, "which", return_value=None), \
                mock.patch.object(uninstall, "_openclaw_dir", return_value=""), \
                mock.patch.object(storage, "TRACES_DIR", self.tmp / "no-traces"), \
                mock.patch.object(storage.features, "effective_model_store", return_value=str(self.tmp / "ollama")):
            s = storage.scan(self.profile, status)
        names = {e.name: e for e in s.entries}
        self.assertEqual(names["qwen3.5:9b"].bytes, 6_600_000_000)
        self.assertNotIn("gpt-oss:20b", names)                        # not downloaded: no space taken
        self.assertEqual(names["ae.safetensors"].group, "Models")
        self.assertEqual(names["Image generation (ComfyUI)"].bytes, 2_000_000)   # the models are counted once
        self.assertEqual(names["someone/thing"].level, "off")          # not the stack's download
        self.assertIn("voice typing", names["Whisper small"].note)
        self.assertEqual(names["Images and transcripts made"].bytes, 500)
        self.assertEqual(s.problems, [])
        self.assertEqual(sum(s.by_drive().values()), s.total())

    def test_size_text(self):
        self.assertEqual(storage.size_text(1_500_000_000), "1.5 GB")
        self.assertEqual(storage.size_text(12_000_000), "12 MB")
        self.assertEqual(storage.size_text(0), "0")


class Processes(Temp):
    def test_runner_rows_name_their_model(self):
        store = self.tmp / "models"
        manifest = features.manifest_path(str(store), "qwen3.5:9b")
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"layers": [{"mediaType": modules.MODEL_LAYER, "digest": "sha256:abc"}]}),
                            encoding="utf-8")
        runner = SimpleNamespace(pid=30, cmdline=lambda: ["llama-server.exe", "--model", str(store / "blobs" / "sha256-abc"),
                                                          "-c", "32768"])
        server = SimpleNamespace(pid=20, info={"pid": 20, "name": "ollama.exe"}, cmdline=lambda: ["ollama.exe", "serve"],
                                 children=lambda: [runner])
        app = SimpleNamespace(info={"pid": 10, "name": "ollama app.exe"}, cmdline=lambda: ["ollama app.exe"])
        fake = SimpleNamespace(process_iter=lambda attrs: [app, server], Error=Exception)
        with mock.patch.object(modules, "_psutil", return_value=fake):
            tree = modules.ollama_tree([{"name": "qwen3.5:9b"}])
        self.assertEqual(tree, {"pid": 20, "runners": [{"pid": 30, "model": "qwen3.5:9b", "context": 32768}]})

    def test_arguments(self):
        self.assertEqual(modules._arg(["x", "--model=a b", "-c", "9"], "--model", "-m"), "a b")
        self.assertEqual(modules._arg(["x", "-c", "9"], "-c"), "9")
        self.assertEqual(modules._arg(["x"], "-c"), "")


class TrayButtons(unittest.TestCase):
    def test_feature_buttons(self):
        import tray

        b = tray.TrayApp._feature_buttons
        self.assertEqual(b("models", S(True, True, "Installed")), (False, ""))
        self.assertEqual(b("models", S(False, True, "Models missing", level="warn")), (True, ""))
        self.assertEqual(b("gateway", S(False, True, "Not installed", level="bad")), (False, "Install"))
        self.assertEqual(b("chat", S(True, True, "Installed")), (False, "Remove"))
        self.assertEqual(b("chat", S(True, False, "Installed, off", level="off")), (False, "Remove"))
        self.assertEqual(b("chat", S(False, False, "Not installed", level="off")), (False, "Install"))
        self.assertEqual(b("images", S(False, True, "Model missing", level="warn")), (True, "Remove"))
        # No longer offered (Claude Desktop is closed source): Remove only, and nothing at all once it is gone.
        self.assertEqual(b("recordings", S(True, False, "Not in Claude Desktop", level="off")), (False, "Remove"))
        self.assertEqual(b("recordings", S(False, True, "Files missing", level="warn")), (False, "Remove"))
        self.assertEqual(b("recordings", S(False, False, "Not installed", level="off")), (False, ""))
        self.assertEqual(b("chat", S(False, True, features.NOT_CHECKED, level="warn")), (False, ""))
        self.assertEqual(b("chat", None), (False, ""))

    def test_model_lines(self):
        import tray

        row = lambda **k: uninstall.ModelRow(**{"name": "m", "size_gb": 1.0, "downloaded": True, "use": "",  # noqa: E731
                                                "in_catalog": True, "role": "primary", **k})
        self.assertEqual(tray.model_line(row(use="chat")), "in use: chat")
        self.assertEqual(tray.model_line(row()), "chat model, not used by the stack")
        self.assertEqual(tray.model_line(row(downloaded=False, role="reviewer", use="reviewer")),
                         "code review model, not downloaded; Settings names it for reviewer")


if __name__ == "__main__":
    unittest.main()
