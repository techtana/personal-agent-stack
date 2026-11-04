"""Tests for scripts/stacklib/media.py: ComfyUI service command, saved workflows and Open WebUI provisioning."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import media, profile as prof  # noqa: E402


def make_profile(root: str, comfyui: str = "native") -> dict:
    return {
        "name": "TEST",
        "ports": {"comfyui": 8188, "kokoro": 8880, "ollama": 11434},
        "services": {"comfyui": comfyui},
        "media": prof.resolve_media({"comfyui_args": ["--lowvram"], "image_workflow": "z_image_turbo",
                                     "image_size": "1024x1024", "image_steps": 8}, {"root": root}),
        "agent_access": {"allowed_roots": [root]},
        "ollama_env": {},
        "model_store": "",
    }


class ResolveMedia(unittest.TestCase):
    def test_folders_default_below_the_root(self):
        m = prof.resolve_media({}, {"root": r"D:\media"})
        self.assertEqual(m["comfyui_dir"], r"D:\media\comfyui")
        self.assertEqual(m["models_dir"], r"D:\media\comfyui\models")
        self.assertEqual(m["uv_cache"], r"D:\media\.uv-cache")

    def test_posix_root(self):
        self.assertEqual(prof.resolve_media({}, {"root": "/srv/media/"})["output_dir"], "/srv/media/outputs")

    def test_no_root_no_folders(self):
        self.assertNotIn("comfyui_dir", prof.resolve_media({}, {}))


class Workflows(unittest.TestCase):
    def test_node_map_points_at_existing_nodes(self):
        for wf_file in media.WORKFLOWS_DIR.glob("*.json"):
            if wf_file.name.endswith(".nodes.json"):
                continue
            wf, nodes = media.load_workflow(wf_file.stem)
            for entry in nodes:
                for nid in entry["node_ids"]:
                    self.assertIn(nid, wf, f"{wf_file.name}: node {nid}")
                    self.assertIn(entry["key"], wf[nid]["inputs"], f"{wf_file.name}: {nid}.{entry['key']}")

    def test_every_model_file_in_a_workflow_is_listed_with_an_open_licence(self):
        listed = {m.name: m for m in media.MODELS}
        for wf_file in media.WORKFLOWS_DIR.glob("*.json"):
            if wf_file.name.endswith(".nodes.json"):
                continue
            wf = json.loads(wf_file.read_text(encoding="utf-8"))
            for node in wf.values():
                for key, value in node["inputs"].items():
                    if isinstance(value, str) and value.endswith((".safetensors", ".pth", ".ckpt", ".gguf")):
                        self.assertIn(value, listed, f"{wf_file.name}: {value} missing from media.MODELS")
                        self.assertIn(listed[value].licence, media.OPEN_LICENCES)

    def test_models_md_lists_every_model(self):
        text = (media.COMFY_DIR / "MODELS.md").read_text(encoding="utf-8")
        for m in media.MODELS:
            self.assertIn(m.name, text)


class Settings(unittest.TestCase):
    def test_image_settings_follow_the_profile(self):
        s = media.image_settings(make_profile(r"D:\media"))
        self.assertIs(s["image_generation.enable"], True)
        self.assertEqual(s["image_generation.engine"], "comfyui")
        self.assertEqual(s["image_generation.comfyui.base_url"], "http://127.0.0.1:8188")
        self.assertEqual(s["image_generation.model"], "z_image_turbo_int8_convrot.safetensors")
        self.assertEqual(s["image_generation.steps"], 8)
        json.loads(s["image_generation.comfyui.workflow"])

    def test_off_means_no_settings(self):
        self.assertEqual(media.image_settings(make_profile(r"D:\media", comfyui="off")), {})
        self.assertEqual(media.openwebui_env(make_profile(r"D:\media", comfyui="off")), {})

    def test_comfyui_command(self):
        spec = media.service_command(make_profile(r"D:\media"), "comfyui", {})
        self.assertIn("main.py", spec["cmd"])
        self.assertEqual(spec["cmd"][spec["cmd"].index("--port") + 1], "8188")
        self.assertEqual(spec["cmd"][spec["cmd"].index("--listen") + 1], "127.0.0.1")
        self.assertIn("--lowvram", spec["cmd"])
        self.assertEqual(spec["cwd"], r"D:\media\comfyui")


class Provision(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "webui.db"
        con = sqlite3.connect(self.db)
        con.execute('CREATE TABLE config ("key" TEXT NOT NULL, value JSON NOT NULL, updated_at BIGINT, PRIMARY KEY ("key"))')
        con.execute("insert into config values ('image_generation.enable', 'false', 0)")
        con.execute("insert into config values ('ui.other', '\"kept\"', 0)")
        con.commit()
        con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self):
        con = sqlite3.connect(self.db)
        try:
            return dict(con.execute("select key, value from config").fetchall())
        finally:
            con.close()

    def test_writes_changed_keys_and_backs_up(self):
        changed = media.provision_openwebui(self.db, {"image_generation.enable": True, "image_generation.steps": 8})
        self.assertEqual(changed, ["image_generation.enable", "image_generation.steps"])
        rows = self.rows()
        self.assertEqual(json.loads(rows["image_generation.enable"]), True)
        self.assertEqual(json.loads(rows["ui.other"]), "kept")
        self.assertEqual(len(list(Path(self.tmp.name).glob("webui.db.bak-*"))), 1)

    def test_second_run_changes_nothing(self):
        media.provision_openwebui(self.db, {"image_generation.enable": True})
        self.assertEqual(media.provision_openwebui(self.db, {"image_generation.enable": True}), [])
        self.assertEqual(len(list(Path(self.tmp.name).glob("webui.db.bak-*"))), 1)

    def test_missing_database_is_left_to_the_environment(self):
        self.assertEqual(media.provision_openwebui(Path(self.tmp.name) / "none.db", {"x": 1}), [])


class GuardedInstall(unittest.TestCase):
    def test_install_refuses_a_root_outside_the_list(self):
        p = make_profile(r"D:\media")
        p["agent_access"]["allowed_roots"] = [r"E:\elsewhere"]
        with self.assertRaises(PermissionError):
            media.install_models(p, "z_image_turbo")


if __name__ == "__main__":
    unittest.main()
