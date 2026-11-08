"""The installer's catalog, config/installer.yaml (stacklib/catalog.py): every version, URL, model list and size the
installer uses, read from one file. These tests keep the file complete and the code's constants in step with it."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from stacklib import catalog, features, install, media, services, settings, winget_build  # noqa: E402
from stacklib import dictation  # noqa: E402
from stacklib.dictation import models as wmodels, speak  # noqa: E402

DEFAULTS = yaml.safe_load((REPO / "machines" / "_defaults.yaml").read_text(encoding="utf-8"))


class File(unittest.TestCase):
    def test_it_parses_and_has_every_section(self):
        data = catalog.load()
        self.assertEqual(data["schema_version"], 1)
        for section in ("ollama", "models", "context_choices", "python_tools", "images", "whisper", "kokoro",
                        "openclaw", "winget", "features"):
            self.assertIn(section, data, f"config/installer.yaml lost its {section} section")

    def test_a_broken_file_says_which_file(self):
        with self.assertRaises(catalog.CatalogError) as cm:
            catalog.load.__wrapped__(REPO / "config" / "no-such-catalog.yaml")
        self.assertIn("no-such-catalog.yaml", str(cm.exception))

    def test_the_old_model_catalog_moved_out_of_the_defaults(self):
        self.assertNotIn("model_catalog", DEFAULTS)


class Models(unittest.TestCase):
    def test_every_model_a_hardware_class_names_is_in_the_catalog(self):
        cat = catalog.models()
        for cls in DEFAULTS["hardware_classes"]:
            for role, name in cls["models"].items():
                if name:
                    with self.subTest(hardware_class=cls["name"], role=role):
                        self.assertIn(name, cat)
                        self.assertGreater(float(cat[name]["size_gb"]), 0)

    def test_measured_figures_are_complete(self):
        for (model, ctx), (vram, ram, speed) in catalog.measured_models().items():
            self.assertIn(model, catalog.models())
            self.assertIn(ctx, catalog.context_choices())
            self.assertGreater(vram, 0)
            self.assertGreaterEqual(ram, 0)
            self.assertGreater(speed, 0)

    def test_the_default_chat_model_is_offered(self):
        self.assertIn(catalog.ollama()["default_chat_model"], catalog.models())
        self.assertEqual(settings.CTX_CHOICES, [str(n) for n in catalog.context_choices()])


class Tools(unittest.TestCase):
    def test_python_tools(self):
        tools = catalog.python_tools()
        for tid in ("litellm", "phoenix", "open-webui", "hf"):
            with self.subTest(tool=tid):
                t = tools[tid]
                self.assertTrue(t["env"] and t["script"] and t["install"] and re.fullmatch(r"3\.\d+", str(t["python"])))
        self.assertTrue(any("==" in str(a) for a in tools["litellm"]["install"]), "the gateway's LiteLLM is pinned")
        self.assertEqual([t[0] for t in install.TOOLS], ["litellm", "phoenix", "open-webui"])
        self.assertEqual(install.HF_TOOL[0], tools["hf"]["env"])
        self.assertEqual(services.TOOL_SCRIPTS["open_webui"], (tools["open-webui"]["env"], tools["open-webui"]["script"]))

    def test_compiled_packages_are_pinned(self):
        """Smart App Control judges compiled modules version by version: a floating version is an untested one."""
        for pkg in ("faster-whisper", "ctranslate2", "onnxruntime", "av", "numpy", "tokenizers"):
            with self.subTest(package=pkg):
                self.assertTrue(any(p.startswith(pkg + "==") for p in dictation.PACKAGES), f"{pkg} is not pinned")
        for p in (*dictation.READ_PACKAGES, *dictation.READ_GPU_PACKAGES):
            self.assertIn("==", p)
        self.assertTrue(dictation.READ_GPU_PACKAGES[0].startswith("onnxruntime-gpu=="))
        self.assertIn("av==17.0.0", media.SAC_PINS)

    def test_node_versions_for_openclaw(self):
        ok = install.node_ok_for_openclaw
        self.assertTrue(ok((24, 22, 1)))
        self.assertFalse(ok((24, 22, 0)))
        self.assertFalse(ok((25, 0, 0)))
        self.assertTrue(ok((26, 12, 1)))
        self.assertTrue(ok((30, 0, 0)))
        self.assertFalse(ok(None))
        self.assertIn("24.22.1+", install.node_requirement())

    def test_winget_lists(self):
        ids = [r for r, *_ in winget_build.OWNER_PACKAGES + winget_build.EDGE_PACKAGES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(winget_build.package_id("git"), "Git.Git")
        self.assertEqual(winget_build.package_id("ollama"), catalog.ollama()["winget_id"])


class Media(unittest.TestCase):
    def test_image_models_come_from_the_catalog(self):
        files = [f["file"] for wf in catalog.images()["workflows"].values() for f in wf["models"]]
        self.assertEqual([m.name for m in media.MODELS], files)
        self.assertEqual(media.WORKFLOW_LABELS["z_image_turbo"], "Z-Image-Turbo int8")
        self.assertTrue(media.COMFYUI_GIT.startswith("https://"))
        for m in media.MODELS:
            self.assertIn(m.licence, media.OPEN_LICENCES)

    def test_whisper_models(self):
        offered = catalog.whisper_models()
        self.assertEqual(wmodels.CHOICES, list(offered))
        for name, m in offered.items():
            with self.subTest(model=name):
                self.assertIn("/", m["repo"])
                self.assertEqual(features.WHISPER[name], (m["download_gb"], m["vram_gb"], m["s_per_15s"]))
        for key in ("model", "cpu_model"):
            self.assertIn(DEFAULTS["dictation"][key], offered)
        self.assertEqual(wmodels.repo_for("turbo"), offered["large-v3-turbo"]["repo"])

    def test_kokoro(self):
        k = catalog.kokoro()
        self.assertRegex(k["revision"], r"^[0-9a-f]{40}$")
        self.assertEqual(set(speak.KOKORO_FILES), {"fp32", "int8"})
        self.assertIn(DEFAULTS["read_aloud"]["voice"], speak.KOKORO_VOICE_IDS)
        self.assertTrue(set(speak.DEFAULT_FOR_LANGUAGE.values()) <= set(speak.KOKORO_VOICE_IDS))
        self.assertEqual(features.KOKORO["fp32"][1], k["variants"]["fp32"]["download_gb"])
        self.assertEqual(features.KOKORO_GPU_GB, k["gpu_libraries_gb"])

    def test_every_feature_has_a_footprint(self):
        for f in features.FEATURES:
            if f.id in ("models", "read_aloud"):   # counted from the model tables
                continue
            with self.subTest(feature=f.id):
                self.assertGreater(catalog.feature_footprint(f.id)["disk_gb"], 0)


if __name__ == "__main__":
    unittest.main()
