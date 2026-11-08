"""Tests for the feature catalog, its load estimates and fit check, and the installed/linked status
(stacklib/features.py), which the installer's features page, the tray's Features card and `stack.py features` share.

Run with `uv run --with pytest python -m pytest -q tests/test_features.py`.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from stacklib import clients, features, profile as prof  # noqa: E402

DEFAULTS = yaml.safe_load((REPO / "machines" / "_defaults.yaml").read_text(encoding="utf-8"))
REFERENCE_PC = {"gpu": "NVIDIA GeForce RTX 3060", "vram_mib": 12288, "idle_vram_mib": 1135, "ram_gb": 31.9}


def make_profile(store: Path, detected: dict | None = None, **over) -> dict:
    p = {
        "name": "TESTBOX",
        "detected": dict(REFERENCE_PC if detected is None else detected),
        "models": {"fim": "qwen2.5-coder:1.5b-base", "embed": "nomic-embed-text", "small": "qwen3.5:9b",
                   "primary": "qwen3.5:9b", "primary_num_ctx": 32768, "small_num_ctx": 32768},
        "catalog": DEFAULTS["model_catalog"],
        "ollama_env": {"OLLAMA_MODELS": str(store), "OLLAMA_KEEP_ALIVE": "4h", "OLLAMA_KV_CACHE_TYPE": "q8_0"},
        "model_store": str(store),
        "services": dict(DEFAULTS["services"]),
        "observability": dict(DEFAULTS["observability"]),
        "ports": dict(DEFAULTS["ports"]),
        "media": {},
        "dictation": {"model": "large-v3-turbo", "unload_after_min": 30},
        "data_dir": store,
    }
    p.update(over)
    return p


def hw(vram_gb: float = 12.0, desktop: float = 1.1, ram: float = 32.0, threads: int = 12, sac: bool = False):
    return features.Hardware(gpu="GPU", vram_gb=vram_gb, desktop_vram_gb=desktop if vram_gb else 0.0, ram_gb=ram,
                             threads=threads, smart_app_control=sac)


class TempStore(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        # The Whisper model's cache state comes from this PC's HF_HOME; tests say it explicitly.
        patcher = mock.patch.object(features, "_whisper_cached", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def pull(self, *models: str) -> None:
        for m in models:
            path = features.manifest_path(str(self.tmp), m)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")


class Catalog(unittest.TestCase):
    def test_ids_are_unique_and_the_core_is_required(self):
        ids = [f.id for f in features.FEATURES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual({f.id for f in features.FEATURES if f.required}, {"models", "gateway"})

    def test_every_service_belongs_to_one_feature_or_says_why_not(self):
        names = set(DEFAULTS["services"])
        claimed = [svc for f in features.FEATURES for svc in f.services]
        self.assertEqual(len(claimed), len(set(claimed)), "a service belongs to two features")
        self.assertEqual(set(claimed) - names, set(), "a feature names a service that does not exist")
        self.assertEqual(names - set(claimed) - set(features.NOT_INSTALLABLE), set(),
                         "add each new service to a feature in stacklib/features.py, or to NOT_INSTALLABLE with why")
        self.assertEqual(set(features.NOT_INSTALLABLE) & set(claimed), set())

    def test_every_feature_has_an_estimate_and_a_status_check(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(features, "_whisper_cached", return_value=False):
            est = features.estimates(make_profile(Path(d)), hw())
        self.assertEqual(set(est), {f.id for f in features.FEATURES})
        self.assertEqual(set(features._STATUS), {f.id for f in features.FEATURES})


class Hardware(unittest.TestCase):
    def test_reads_the_detected_block(self):
        with mock.patch.object(features, "smart_app_control_on", return_value=True):
            h = features.hardware({"detected": REFERENCE_PC})
        self.assertEqual(h.vram_gb, 12.0)
        self.assertAlmostEqual(h.gpu_free_gb, 10.89, places=2)
        self.assertTrue(h.smart_app_control)
        self.assertIn("12.0 GB of GPU memory", h.describe())

    def test_no_gpu(self):
        with mock.patch.object(features, "smart_app_control_on", return_value=False):
            h = features.hardware({"detected": {"gpu": None, "vram_mib": 0, "idle_vram_mib": None, "ram_gb": 16}})
        self.assertEqual((h.vram_gb, h.gpu_free_gb), (0.0, 0.0))
        self.assertIn("no NVIDIA GPU", h.describe())

    def test_a_model_loaded_when_doctor_measured_does_not_count_as_the_desktop(self):
        with mock.patch.object(features, "smart_app_control_on", return_value=False):
            h = features.hardware({"detected": {**REFERENCE_PC, "idle_vram_mib": 8029}})   # the 9B was loaded
        self.assertEqual(h.desktop_vram_gb, features.DESKTOP_VRAM_MAX)


class ChatModelMemory(TempStore):
    def test_measured_on_the_reference_pc(self):
        vram, ram, basis, speed = features.chat_model_memory(make_profile(self.tmp), hw())
        self.assertEqual((vram, ram, speed), (5.7, 0.0, 51))
        self.assertIn("Measured", basis)

    def test_ollamas_own_figures_win_when_the_model_is_loaded(self):
        loaded = [{"name": "qwen3.5:9b", "context_length": 32768, "size": 6166413310, "size_vram": 6166413310}]
        vram, ram, basis, _ = features.chat_model_memory(make_profile(self.tmp), hw(), loaded)
        self.assertAlmostEqual(vram, 5.74, places=2)
        self.assertEqual(ram, 0.0)
        self.assertIn("measured now", basis)

    def test_a_loaded_model_with_another_context_is_not_used(self):
        loaded = [{"name": "qwen3.5:9b", "context_length": 8192, "size": 10**9, "size_vram": 10**9}]
        self.assertEqual(features.chat_model_memory(make_profile(self.tmp), hw(), loaded)[0], 5.7)

    def test_a_smaller_card_splits_the_model(self):
        vram, ram, basis, speed = features.chat_model_memory(make_profile(self.tmp), hw(vram_gb=6.0, desktop=1.0))
        self.assertLessEqual(vram, 5.0)
        self.assertAlmostEqual(vram + ram, 5.7, places=6)
        self.assertEqual(speed, 0)   # the measured speed was for the whole model on the card
        self.assertIn("splits", basis)

    def test_no_gpu_puts_it_all_in_system_ram(self):
        vram, ram, _, _ = features.chat_model_memory(make_profile(self.tmp), hw(vram_gb=0))
        self.assertEqual((vram, ram), (0.0, 5.7))

    def test_unmeasured_model_is_estimated_from_size_and_context(self):
        p = make_profile(self.tmp)
        p["models"].update(primary="gpt-oss:20b", primary_num_ctx=16384)
        vram, ram, basis, _ = features.chat_model_memory(p, hw(vram_gb=24.0, desktop=1.0))
        self.assertAlmostEqual(vram, 13e9 / 2**30 + 1.0 + 0.3, places=6)   # q8_0: 2 GB per 32k, so 1 GB at 16k
        self.assertEqual(ram, 0.0)
        self.assertIn("Estimate", basis)


class Downloads(TempStore):
    def test_pulled_models_are_not_downloaded_again(self):
        p = make_profile(self.tmp)
        self.assertIsNone(features.estimate("models", p, hw()).todo_gb)   # nothing pulled: the whole size
        self.pull("nomic-embed-text", "qwen3.5:9b")
        self.assertAlmostEqual(features.estimate("models", p, hw()).todo_gb, 1.0)   # the FIM model is left
        self.assertEqual(features.missing_models(p), ["qwen2.5-coder:1.5b-base"])

    def test_the_shared_whisper_model_counts_once_and_installed_features_not_at_all(self):
        est = features.estimates(make_profile(self.tmp), hw())
        both = features.download_gb(["voice_typing", "recordings"], est)
        self.assertAlmostEqual(both, 0.3 + 2.4 + 1.6)
        self.assertAlmostEqual(features.download_gb(["voice_typing", "recordings"], est, {"recordings"}), 0.3 + 1.6)
        with mock.patch.object(features, "_whisper_cached", return_value=True):
            est = features.estimates(make_profile(self.tmp), hw())
        self.assertAlmostEqual(features.download_gb(["voice_typing", "recordings"], est), 0.3 + 2.4)

    def test_manifest_paths(self):
        store = "S"
        self.assertEqual(features.manifest_path(store, "nomic-embed-text"),
                         Path("S/manifests/registry.ollama.ai/library/nomic-embed-text/latest"))
        self.assertEqual(features.manifest_path(store, "someone/model:7b"),
                         Path("S/manifests/registry.ollama.ai/someone/model/7b"))
        self.assertEqual(features.manifest_path(store, "hf.co/org/repo:Q4_K_M"),
                         Path("S/manifests/hf.co/org/repo/Q4_K_M"))


class Assess(TempStore):
    def levels(self, chosen, machine, installed=frozenset(), profile=None) -> dict[str, str]:
        est = features.estimates(profile or make_profile(self.tmp), machine)
        found = features.assess(chosen, est, machine, installed)
        return {f.text.split(":")[0].split(" ")[0]: f.level for f in found} | {"_texts": " | ".join(f.text for f in found)}

    def test_the_reference_pc_with_everything(self):
        out = self.levels([f.id for f in features.FEATURES], hw())
        self.assertEqual(out["GPU"], "ok", out["_texts"])      # 5.7 + 0.4 + 1.2 + 1.1 = 8.4 of 10.9 GB
        self.assertEqual(out["An"], "warn")                     # an image next to them spills to system RAM
        self.assertIn("Click Media", out["_texts"])
        self.assertEqual(out["System"], "ok")
        self.assertEqual(out["CPU"], "ok")

    def test_images_alone_fit_next_to_the_chat_model_on_a_24_gb_card(self):
        out = self.levels(["images"], hw(vram_gb=24.0))
        self.assertEqual(out["An"], "ok", out["_texts"])

    def test_a_card_smaller_than_an_image_job(self):
        out = self.levels(["images"], hw(vram_gb=8.0, desktop=0.5))
        self.assertIn("more than the card has free", out["_texts"])

    def test_whisper_next_to_the_chat_model_on_an_8_gb_card(self):
        out = self.levels(["voice_typing", "recordings"], hw(vram_gb=8.0, desktop=1.0))
        self.assertEqual(out["GPU"], "warn", out["_texts"])   # 5.7 + 1.2 + 1.1 > 7.0
        self.assertIn("several times slower", out["_texts"])

    def test_no_gpu(self):
        out = self.levels(["chat"], hw(vram_gb=0))
        self.assertEqual(out["No"], "bad")
        self.assertEqual(out["CPU"], "warn")

    def test_little_ram(self):
        out = self.levels(["images"], hw(ram=16.0))
        self.assertEqual(out["System"], "warn", out["_texts"])   # up to ~11.5 GB after an image job, of 16

    def test_smart_app_control_warns_about_phoenix_only_when_it_would_be_installed(self):
        self.assertIn("Smart App Control", self.levels(["tracing"], hw(sac=True))["_texts"])
        self.assertNotIn("Smart App Control", self.levels(["tracing"], hw(sac=True), {"tracing"})["_texts"])
        self.assertNotIn("Smart App Control", self.levels(["chat"], hw(sac=True))["_texts"])

    def test_nothing_new_to_download(self):
        self.pull(*features.models_to_pull(make_profile(self.tmp)))
        everything = {f.id for f in features.FEATURES}
        out = self.levels(["chat"], hw(), installed=everything)
        self.assertIn("Nothing new to download. Open WebUI is installed already.", out["_texts"])

    def test_required_features_always_count(self):
        est = features.estimates(make_profile(self.tmp), hw())
        text = " ".join(f.text for f in features.assess([], est, hw()))
        self.assertIn("chat model 5.7", text)


class Text(TempStore):
    def test_cells_and_detail_say_what_the_load_is(self):
        est = features.estimates(make_profile(self.tmp), hw())
        c = features.cells(est["images"], hw())
        self.assertEqual((c["vram"], c["ram"], c["disk"]), ("0.4 to 10.5", "1.5 to 9.5", "16.8"))
        self.assertEqual(features.cells(est["gateway"], hw())["vram"], "-")
        self.assertEqual(features.cells(est["chat"], hw())["cpu"], "under 1 of 12")
        detail = features.detail_text(est["voice_typing"])
        for part in ("GPU:", "CPU:", "Memory: 1.2 GB of GPU memory", "When: Whisper loads on first use", "Disk: 1.9 GB",
                     "shared"):
            self.assertIn(part, detail)
        self.assertIn("GPU 0.4 to 10.5 GB", features.brief(est["images"]))
        self.assertNotIn("GPU", features.brief(est["gateway"]))

    def test_keep_alive_wording(self):
        self.assertEqual(features._keep_text("4h"), "4 hours after the last request")
        self.assertEqual(features._keep_text("1h"), "1 hour after the last request")
        self.assertEqual(features._keep_text("-1"), "until Ollama stops")


class Statuses(TempStore):
    def setUp(self):
        super().setUp()
        self.media = self.tmp / "media"
        self.p = make_profile(self.tmp, media=prof.resolve_media({}, {"root": str(self.media)}),
                              agent_access={"allowed_roots": [str(self.media)]})
        gateway_only = clients.ClientStatus("ok", "Gateway only", "Every model it calls goes through the gateway.")
        for target, value in ((features, "which"), (features, "_tool_env"), (features, "desktop_entry")):
            patcher = mock.patch.object(target, value)
            setattr(self, value, patcher.start())
            self.addCleanup(patcher.stop)
        self.which.side_effect = lambda name: f"/bin/{name}"
        self._tool_env.side_effect = lambda env: self.tmp / env if env in ("litellm", "open-webui") else None
        self.desktop_entry.return_value = None
        self.openclaw = gateway_only

    def status(self) -> dict[str, features.Status]:
        return features.statuses(self.p, openclaw=self.openclaw)

    def test_switches(self):
        self.p["services"]["open_webui"] = "native"
        self.p["observability"]["phoenix"] = False
        s = self.status()
        self.assertEqual((s["chat"].state, s["chat"].locked), ("Installed", True))
        self.assertEqual((s["tracing"].state, s["tracing"].level), ("Not installed", "off"))
        self.p["services"]["open_webui"] = "off"
        self.p["observability"]["phoenix"] = True
        s = self.status()
        self.assertEqual((s["chat"].state, s["chat"].locked, s["chat"].installed), ("Installed, off", False, True))
        self.assertEqual((s["tracing"].state, s["tracing"].level), ("Not installed", "warn"))   # on, but missing

    def test_models_missing_is_not_a_missing_program(self):
        s = self.status()
        self.assertEqual(s["models"].state, "Models missing")
        self.assertIs(features.service_installed("ollama", s), True)
        self.pull(*features.models_to_pull(self.p))
        self.assertEqual(self.status()["models"].state, "Installed")
        self.which.side_effect = lambda name: None
        s = self.status()
        self.assertEqual((s["models"].state, s["models"].level), ("Not installed", "bad"))
        self.assertIs(features.service_installed("ollama", s), False)

    def test_recordings_are_linked_through_claude_desktop(self):
        self.assertEqual(self.status()["recordings"].state, "Not installed")
        self.desktop_entry.return_value = {"command": "python"}
        self.assertEqual(self.status()["recordings"].state, "Files missing")
        from stacklib import whisper

        whisper.whisper_python(self.p).parent.mkdir(parents=True)
        whisper.whisper_python(self.p).write_text("", encoding="utf-8")
        (whisper.whisper_dir(self.p) / "whisper_mcp.py").write_text("", encoding="utf-8")
        self.assertEqual((self.status()["recordings"].state, self.status()["recordings"].locked), ("Linked", True))
        self.desktop_entry.return_value = None
        s = self.status()["recordings"]
        self.assertEqual((s.state, s.installed, s.on), ("Not in Claude Desktop", True, False))

    def test_desktop_entry_reads_claude_desktops_config(self):
        config = self.tmp / "claude_desktop_config.json"
        from stacklib import whisper

        with mock.patch.object(whisper, "desktop_config_path", return_value=config):
            config.write_text(json.dumps({"mcpServers": {"other": {}}}), encoding="utf-8")
            self.assertIsNone(_real_desktop_entry())
            config.write_text(json.dumps({"mcpServers": {whisper.SERVER_NAME: {"command": "py"}}}), encoding="utf-8")
            self.assertEqual(_real_desktop_entry(), {"command": "py"})
            config.write_text("{not json", encoding="utf-8")
            self.assertIsNone(_real_desktop_entry())
            config.write_text(json.dumps({"mcpServers": {whisper.SERVER_NAME: {"command": "py"}}}), encoding="utf-8-sig")
            self.assertEqual(_real_desktop_entry(), {"command": "py"})   # saved with a byte order mark

    def test_openclaw(self):
        self.assertEqual(self.status()["openclaw"].state, "Gateway only")
        self.openclaw = clients.ClientStatus("warn", "Bypasses the gateway", "talks to Ollama directly")
        s = self.status()["openclaw"]
        self.assertEqual((s.installed, s.on, s.level), (True, False, "warn"))
        self.which.side_effect = lambda name: None if name == "openclaw" else f"/bin/{name}"
        self.assertEqual(self.status()["openclaw"].state, "Not installed")

    def test_an_unknown_tool_folder_is_not_checked_rather_than_missing(self):
        from stacklib import services

        self._tool_env.side_effect = _ORIGINAL_TOOL_ENV
        with mock.patch.object(services, "_uv_tool_dir", return_value=None):
            s = self.status()
        self.assertEqual(s["gateway"].state, "Not checked")
        self.assertIsNone(features.service_installed("litellm", s))   # the tray leaves LiteLLM's Start button alone
        with mock.patch.object(services, "_uv_tool_dir", return_value=self.tmp):
            (self.tmp / "litellm").mkdir()
            (self.tmp / "litellm" / "pyvenv.cfg").write_text("", encoding="utf-8")
            s = self.status()
        self.assertEqual((s["gateway"].state, s["chat"].installed), ("Installed", False))

    def test_a_failing_check_reads_not_checked(self):
        with mock.patch.dict(features._STATUS, {"chat": mock.Mock(side_effect=OSError("disk gone"))}):
            s = self.status()
        self.assertEqual((s["chat"].state, s["chat"].detail), ("Not checked", "disk gone"))
        self.assertIsNone(features.service_installed("open_webui", s))
        self.assertNotIn("chat", features.not_installed(s))


def _real_desktop_entry():
    """features.desktop_entry without the mock the Statuses tests put on it."""
    return _ORIGINAL_DESKTOP_ENTRY()


_ORIGINAL_DESKTOP_ENTRY = features.desktop_entry
_ORIGINAL_TOOL_ENV = features._tool_env


class Choice(unittest.TestCase):
    S = features.Status

    def test_first_ticks(self):
        status = {
            "models": self.S(True, True, "Installed"), "gateway": self.S(False, True, "Not installed", level="bad"),
            "chat": self.S(True, False, "Installed, off", level="off"),
            "tracing": self.S(False, False, "Not installed", level="off"),
            "images": self.S(False, False, "Not installed", level="off"),
            "voice_typing": self.S(True, True, "Installed"),
            "recordings": self.S(False, False, "Not installed", level="off"),
            "openclaw": self.S(True, False, "Bypasses the gateway", level="warn"),
        }
        choice = features.initial_choice(status, hw(sac=True))
        self.assertTrue(choice["gateway"])          # required, even when missing
        self.assertTrue(choice["voice_typing"])     # installed and on: kept
        self.assertFalse(choice["chat"])            # turned off on purpose: stays off
        self.assertTrue(choice["openclaw"])         # bypasses the gateway: the installer offers the fix
        self.assertFalse(choice["tracing"])         # Smart App Control blocked Phoenix on the reference PC
        self.assertTrue(choice["images"])           # a 12 GB card
        self.assertFalse(choice["recordings"])
        self.assertFalse(features.initial_choice(status, hw(vram_gb=8.0))["images"])
        self.assertTrue(features.locked("gateway", status) and features.locked("voice_typing", status))
        self.assertFalse(features.locked("chat", status) or features.locked("openclaw", status))

    def test_unknown_and_broken_features(self):
        unknown_on = self.S(False, True, features.NOT_CHECKED, "uv did not answer", "warn")
        unknown_off = self.S(False, False, features.NOT_CHECKED, "uv did not answer", "warn")
        status = {
            "chat": unknown_on, "tracing": unknown_off,
            "images": self.S(False, True, "Model missing", level="warn"),          # on, model gone: repair it
            "voice_typing": self.S(False, True, "Not installed", level="warn"),    # on, program gone: repair it
        }
        choice = features.initial_choice(status, hw(vram_gb=8.0, sac=True))
        self.assertTrue(choice["chat"] and features.locked("chat", status))          # left as it is: on
        self.assertFalse(choice["tracing"] or features.locked("tracing", status))    # off stays off unless ticked
        self.assertTrue(choice["images"])           # though a card under 10 GB is not recommended images
        self.assertTrue(choice["voice_typing"])     # though voice typing is never recommended
        self.assertFalse(features.locked("images", status))   # the owner may still leave it out

    def test_service_rows_follow_their_feature(self):
        status = {"chat": self.S(False, True, "Not installed", level="warn"), "images": self.S(False, False, "Model missing"),
                  "gateway": self.S(False, True, "Not installed", level="bad")}
        self.assertIs(features.service_installed("open_webui", status), False)
        self.assertIs(features.service_installed("comfyui", status), True)
        self.assertIs(features.service_installed("litellm", status), False)
        self.assertIs(features.service_installed("orchestrator", status), True)   # runs from the project itself
        self.assertIsNone(features.service_installed("kokoro", status))
        self.assertIsNone(features.service_installed("phoenix", status))   # not checked yet
        self.assertEqual(features.not_installed(status), ["gateway", "chat", "images"])


class LiveProfile(unittest.TestCase):
    """The real machine profile, read only: every feature gets a status and an estimate, quickly. Whether a check
    fails here ("Not checked") depends on this PC, so that is not asserted."""

    @unittest.skipUnless(prof.machine_file().exists(), "this PC has no machine profile")
    def test_statuses_and_estimates_of_this_pc(self):
        import time

        p = prof.resolve_profile()
        t0 = time.monotonic()
        status = features.statuses(p)
        est = features.estimates(p)
        self.assertLess(time.monotonic() - t0, 30.0)   # `uv tool dir` may time out at 30 s; everything else is fast
        self.assertEqual(set(status), set(est))
        self.assertTrue(all(s.state for s in status.values()))


if __name__ == "__main__":
    unittest.main()
