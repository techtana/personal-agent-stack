"""Tests for the Hugging Face and OpenClaw status shown on the tray's Overview tab (stacklib/clients.py).

Run with `uv run python -m unittest discover -s tests`.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import clients  # noqa: E402

_guards: list = []


def _real_openclaw(*_a, **_k):
    raise AssertionError("a test reached the real OpenClaw setup; mock it inside the test")


def setUpModule():
    # 2026-11-03 a test whose mocks closed before the step ran onboarded the owner's real ~/.openclaw. Tests that want
    # setup_openclaw patch it themselves; anything that slips through fails here before running a command or writing.
    for name in ("setup_openclaw", "_run"):
        g = mock.patch.object(clients, name, _real_openclaw)
        g.start()
        _guards.append(g)


def tearDownModule():
    for g in _guards:
        g.stop()

GATEWAY_CONFIG = """// written by openclaw onboard
{
  agents: {
    defaults: {
      model: { primary: 'stack/docs', fallbacks: ["stack/local-primary",], },
      models: { "stack/docs": { alias: "Docs" } },
    },
  },
  models: {
    providers: {
      stack: { baseUrl: "http://127.0.0.1:4000/v1", api: "openai-completions", apiKey: "${LITELLM_KEY}" },
    },
  },
  /* a block comment with a // inside */
  note: "http://not-a-comment",
}
"""


class Json5(unittest.TestCase):
    def test_reads_comments_trailing_commas_unquoted_keys_and_single_quotes(self):
        c = clients.loads_json5(GATEWAY_CONFIG)
        self.assertEqual(c["agents"]["defaults"]["model"]["primary"], "stack/docs")
        self.assertEqual(c["agents"]["defaults"]["model"]["fallbacks"], ["stack/local-primary"])
        self.assertEqual(c["note"], "http://not-a-comment")

    def test_model_refs_skip_the_alias_table(self):
        refs = clients.model_refs(clients.loads_json5(GATEWAY_CONFIG))
        self.assertEqual(refs, {"stack/docs", "stack/local-primary"})

    def test_model_refs_include_per_agent_and_per_purpose_slots(self):
        c = {"agents": {"defaults": {"model": "a/x", "imageModel": {"primary": "b/y"}},
                        "list": [{"id": "w", "model": "c/z"}]}}
        self.assertEqual(clients.model_refs(c), {"a/x", "b/y", "c/z"})


class EndpointKind(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(clients.endpoint_kind("http://127.0.0.1:4000/v1", 4000), "gateway")
        self.assertEqual(clients.endpoint_kind("http://localhost:11434", 4000), "local")
        self.assertEqual(clients.endpoint_kind("https://api.anthropic.com/v1", 4000), "external")
        self.assertEqual(clients.endpoint_kind("http://192.168.1.5:4000/v1", 4000), "external")


class OpenClaw(unittest.TestCase):
    def check(self, text: str | None, installed: bool = True) -> clients.ClientStatus:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "openclaw.json"
            if text is not None:
                path.write_text(text, encoding="utf-8")
            with mock.patch.object(clients, "which", return_value="openclaw" if installed else None), \
                    mock.patch.dict("os.environ", {"OPENCLAW_CONFIG_PATH": str(path)}):
                return clients.openclaw(4000)

    def test_not_installed_is_off(self):
        self.assertEqual(self.check(None, installed=False).level, "off")

    def test_installed_without_config_asks_for_onboarding(self):
        s = self.check(None)
        self.assertEqual((s.level, s.state), ("warn", "Not set up"))
        self.assertIn("stack.py openclaw", s.detail)

    def test_gateway_only_is_ok(self):
        self.assertEqual(self.check(GATEWAY_CONFIG).level, "ok")

    def test_builtin_cloud_provider_is_bad(self):
        s = self.check('{agents: {defaults: {model: {primary: "anthropic/claude-sonnet-5-5"}}}}')
        self.assertEqual(s.level, "bad")
        self.assertIn("anthropic/claude-sonnet-5-5", s.detail)

    def test_ollama_without_provider_entry_bypasses_the_gateway(self):
        s = self.check('{agents: {defaults: {model: {primary: "ollama/qwen3.5:9b"}}}}')
        self.assertEqual((s.level, s.state), ("warn", "Bypasses the gateway"))

    def test_one_external_fallback_is_enough_to_flag(self):
        s = self.check(GATEWAY_CONFIG.replace('"stack/local-primary"', '"openai/gpt-6"'))
        self.assertEqual(s.level, "bad")

    def test_broken_config_warns(self):
        self.assertEqual(self.check("{agents: ").state, "Unreadable config")


PROFILE = {"ports": {"litellm": 4000}, "models": {"primary_num_ctx": 32768}}


class GatewayPatch(unittest.TestCase):
    def test_makes_the_gateway_the_default_with_no_fallbacks(self):
        p = clients.gateway_patch({}, PROFILE)
        self.assertEqual(p["agents"]["defaults"]["model"], {"primary": "agent-stack/app-dev", "fallbacks": []})
        provider = p["models"]["providers"]["agent-stack"]
        self.assertEqual(provider["baseUrl"], "http://127.0.0.1:4000/v1")
        self.assertEqual(provider["apiKey"]["id"], "LITELLM_MASTER_KEY")  # a reference; the key is not in the file
        ids = [m["id"] for m in provider["models"]]
        self.assertEqual(ids[0], "app-dev")
        self.assertIn("local-primary", ids)
        self.assertTrue(all(m["contextWindow"] == 32768 for m in provider["models"]))

    def test_deletes_slots_and_agent_models_that_leave_the_gateway(self):
        config = {"agents": {"defaults": {"imageModel": {"primary": "openai/gpt-6"}, "utilityModel": "agent-stack/docs"},
                             "entries": {"main": {"model": "anthropic/claude-sonnet-5-5"}, "w": {"model": "agent-stack/docs"}}},
                  "models": {"providers": {"agent-stack": {"baseUrl": "http://127.0.0.1:4000/v1"}}}}
        p = clients.gateway_patch(config, PROFILE)
        self.assertIsNone(p["agents"]["defaults"]["imageModel"])
        self.assertNotIn("utilityModel", p["agents"]["defaults"])
        self.assertEqual(p["agents"]["entries"], {"main": {"model": None}})

    def test_after_the_patch_the_status_is_gateway_only(self):
        config = clients.loads_json5('{agents: {defaults: {model: {primary: "anthropic/x", fallbacks: ["openai/y"]}}}}')
        p = clients.gateway_patch(config, PROFILE)
        merged = {"agents": {"defaults": {**config["agents"]["defaults"], **p["agents"]["defaults"]}}, "models": p["models"]}
        refs = clients.model_refs(merged)
        self.assertTrue(refs and all(clients.ref_kind(merged, r, 4000) == "gateway" for r in refs))

    def test_set_env_line_replaces_only_that_name(self):
        with tempfile.TemporaryDirectory() as d:
            env = Path(d) / ".env"
            env.write_text("A=1\nLITELLM_MASTER_KEY=old\nB=2\n", encoding="utf-8")
            clients.set_env_line(env, "LITELLM_MASTER_KEY", "new")
            self.assertEqual(env.read_text(encoding="utf-8"), "A=1\nB=2\nLITELLM_MASTER_KEY=new\n")


class HuggingFace(unittest.TestCase):
    def check(self, home: str) -> clients.ClientStatus:
        with mock.patch.object(clients, "user_env", return_value=home), \
                mock.patch.object(clients, "which", return_value="hf"):
            return clients.huggingface()

    def test_unset_is_off(self):
        self.assertEqual(self.check("").level, "off")

    def test_missing_drive_is_bad(self):
        s = self.check("Q:\\huggingface" if sys.platform == "win32" else "/nonexistent-mount/hf")
        if sys.platform == "win32" and Path("Q:\\").exists():
            self.skipTest("drive Q: exists here")
        self.assertIn(s.level, ("bad", "ok"))  # on POSIX "/" exists, so only the folder is missing
        if sys.platform == "win32":
            self.assertEqual(s.state, "Drive missing")

    def test_counts_cache_folders_only(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "hub").mkdir()
            (Path(d) / "hub" / "blob").write_bytes(b"x" * 2 * 1024 * 1024)
            (Path(d) / "other.bin").write_bytes(b"x" * 5 * 1024 * 1024)
            s = self.check(d)
        self.assertEqual((s.level, s.state), ("ok", "2 MB"))


if __name__ == "__main__":
    unittest.main()


class InstallerStep(unittest.TestCase):
    """step_openclaw (stacklib/install.py) with OpenClaw already installed."""

    def run_step(self, setup: bool, state: str, setup_result=None):
        """(outcome, setup mock): the step's return value, or the exception it raised."""
        from stacklib import install
        plan = install.Plan(model_store="D:/ollama/models", setup_openclaw=setup)
        fake = mock.Mock(side_effect=setup_result) if setup_result else mock.Mock(return_value="ok")
        with mock.patch.object(install, "which", return_value="openclaw"),                 mock.patch.object(install, "openclaw_state", return_value=state),                 mock.patch.object(install.clients, "setup_openclaw", fake):
            try:
                return install.step_openclaw(plan, PROFILE, lambda *_: None), fake
            except Exception as e:  # noqa: BLE001 - the test inspects it
                return e, fake

    def test_not_chosen_leaves_it_alone(self):
        from stacklib import install
        out, fake = self.run_step(False, "Uses an outside model")
        self.assertIsInstance(out, install.Skip)
        fake.assert_not_called()

    def test_already_private_is_skipped(self):
        from stacklib import install
        out, fake = self.run_step(True, "")
        self.assertIsInstance(out, install.Skip)
        fake.assert_not_called()

    def test_chosen_and_not_private_runs_setup(self):
        out, fake = self.run_step(True, "Not set up")
        self.assertEqual(out, "ok")
        fake.assert_called_once()

    def test_setup_failure_is_a_warning_with_the_fix(self):
        from stacklib import install
        out, _fake = self.run_step(True, "Not set up", RuntimeError("boom"))
        self.assertIsInstance(out, install.Warn)
        self.assertIn("stack.py openclaw", str(out))
