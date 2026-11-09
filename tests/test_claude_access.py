"""Tests for Claude's own keys and the switch that lets Claude use the stack: stacklib/claude_access.py, the gateway's
custom auth (infrastructure/litellm/custom_auth.py), the agent tools' verifier (orchestrator/access.py), and where
they are wired in (settings, services, Claude Code's settings, the Usage tab's client names)."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "infrastructure" / "litellm"))
sys.path.insert(0, str(REPO))

from stacklib import claude_access as ca  # noqa: E402
from stacklib import claude_env, services, usage  # noqa: E402
from stacklib import settings  # noqa: E402

STACK = {"LITELLM_MASTER_KEY": "sk-stack-master", "ORCHESTRATOR_BEARER": "stack-bearer"}


def run(coro):
    return asyncio.run(coro)


class TempDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def profile(self, enabled=None) -> dict:
        p = {"name": "T", "data_dir": self.dir / ".run", "ports": {"litellm": 4000, "orchestrator": 8765}}
        if enabled is not None:
            p["claude_access"] = {"enabled": enabled}
        return p


class SwitchTests(TempDir):
    def test_profile_default_is_on_and_only_false_turns_it_off(self):
        self.assertTrue(ca.enabled({}))
        self.assertTrue(ca.enabled({"claude_access": {}}))
        self.assertTrue(ca.enabled({"claude_access": {"enabled": True}}))
        self.assertFalse(ca.enabled({"claude_access": {"enabled": False}}))

    def test_missing_file_means_the_value_at_start(self):
        missing = self.dir / "none.json"
        self.assertTrue(ca.Switch(missing, default=True).on())
        self.assertFalse(ca.Switch(missing, default=False).on())
        self.assertTrue(ca.Switch(None, default=True).on())

    def test_written_file_is_read_and_followed_when_it_changes(self):
        path = ca.write_switch(self.profile(enabled=False))
        self.assertEqual(path, self.dir / ".run" / ca.SWITCH_NAME)
        switch = ca.Switch(path, default=True)
        self.assertFalse(switch.on())
        ca.write_switch(self.profile(enabled=True))
        self.assertTrue(switch.on())
        ca.write_switch(self.profile(enabled=False))
        self.assertFalse(switch.on())
        self.assertFalse((self.dir / ".run" / (ca.SWITCH_NAME + ".tmp")).exists())

    def test_unclear_profile_values_read_as_off(self):
        for value in (0, "0", "off", "no", "false", "maybe", ""):
            self.assertFalse(ca.enabled({"claude_access": {"enabled": value}}), value)
        for value in (1, "1", "on", "yes", "true", "True"):
            self.assertTrue(ca.enabled({"claude_access": {"enabled": value}}), value)

    def test_a_switch_file_that_goes_away_means_off(self):
        path = ca.write_switch(self.profile(enabled=True))
        switch = ca.Switch(path, default=True)
        self.assertTrue(switch.on())
        path.unlink()
        self.assertFalse(switch.on())     # deleting the file must not bring back the value from the start
        ca.write_switch(self.profile(enabled=True))
        self.assertTrue(switch.on())

    def test_unreadable_file_means_off(self):
        path = self.dir / ca.SWITCH_NAME
        for text in ("{not json", '{"enabled": "yes"}', "[true]", ""):
            path.write_text(text, encoding="utf-8")
            self.assertFalse(ca.Switch(path, default=True).on(), text)

    def test_from_env(self):
        path = ca.write_switch(self.profile(enabled=True))
        self.assertTrue(ca.Switch.from_env({ca.FILE_ENV: str(path), ca.START_ENV: "0"}).on())
        self.assertFalse(ca.Switch.from_env({ca.START_ENV: "0"}).on())
        self.assertTrue(ca.Switch.from_env({}).on())

    def test_service_env(self):
        env = ca.service_env(self.profile(enabled=False))
        self.assertEqual(env[ca.START_ENV], "0")
        self.assertEqual(Path(env[ca.FILE_ENV]), self.dir / ".run" / ca.SWITCH_NAME)


class KeyTests(TempDir):
    def test_missing_keys_are_appended_and_the_rest_of_env_stays(self):
        env = self.dir / ".env"
        env.write_text("# my comment\nLITELLM_MASTER_KEY=sk-stack-master", encoding="utf-8")
        with mock.patch.object(ca, "stack_env_file", side_effect=AssertionError("path was given")):
            keys = ca.ensure_keys(env)
        text = env.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# my comment\nLITELLM_MASTER_KEY=sk-stack-master\n"))
        self.assertTrue(keys[ca.GATEWAY_KEY].startswith("sk-claude-"))
        self.assertGreater(len(keys[ca.TOOLS_KEY]), 30)
        self.assertNotEqual(keys[ca.GATEWAY_KEY], "sk-stack-master")
        self.assertEqual(ca.ensure_keys(env), keys)          # a second call changes nothing
        self.assertEqual(env.read_text(encoding="utf-8"), text)

    def test_the_note_about_new_keys_stays_off_stdout(self):
        # claude-local.ps1 runs every line `stack.py claude-env` prints; a note on stdout would break it
        import contextlib
        import io

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            ca.ensure_keys(self.dir / ".env")
        self.assertEqual(out.getvalue(), "")
        self.assertIn(ca.GATEWAY_KEY, err.getvalue())

    def test_install_generates_them_with_the_other_secrets(self):
        from stacklib import install

        env = self.dir / ".env"
        with mock.patch.object(install, "ENV_FILE", env), \
                mock.patch.object(install, "load_dotenv", side_effect=lambda: {}):
            install.ensure_env_file()
        text = env.read_text(encoding="utf-8")
        for k in (*ca.CLAUDE_KEYS, *STACK):
            self.assertRegex(text, rf"(?m)^{k}=\S+")


class ConnectTests(TempDir):
    def checkout(self, name: str, env: dict | None, extra: dict | None = None) -> Path:
        root = self.dir / name
        (root / ".claude").mkdir(parents=True)
        if env is not None:
            doc = {"env": env, "autoMemoryDirectory": "X:/memory", **(extra or {})}
            (root / ".claude" / "settings.local.json").write_text(json.dumps(doc), encoding="utf-8")
        return root

    def test_connect_swaps_the_stack_keys_for_claudes_and_keeps_everything_else(self):
        env = self.dir / ".env"
        a = self.checkout("main", {**STACK, "OTHER": "1"}, {"enabledMcpjsonServers": ["orchestrator"]})
        b = self.checkout("worktree", {"OTHER": "2"})
        c = self.checkout("bare", None)
        results = dict(ca.connect([a, b, c], env_file=env))
        keys = ca.ensure_keys(env)
        self.assertEqual(set(results.values()), {"updated"})
        self.assertNotIn(ca.settings_file(c), results)       # no settings file: left alone
        doc = json.loads(ca.settings_file(a).read_text(encoding="utf-8"))
        self.assertEqual(doc["env"], {"OTHER": "1", **keys})
        self.assertEqual((doc["autoMemoryDirectory"], doc["enabledMcpjsonServers"]), ("X:/memory", ["orchestrator"]))
        self.assertEqual(json.loads(ca.settings_file(b).read_text(encoding="utf-8"))["env"]["OTHER"], "2")
        self.assertEqual(dict(ca.connect([a, b], env_file=env)), {ca.settings_file(a): "unchanged",
                                                                   ca.settings_file(b): "unchanged"})

    def test_a_stack_key_outside_env_is_reported_not_edited(self):
        env = self.dir / ".env"
        env.write_text("LITELLM_MASTER_KEY=sk-stack-master-0123456789\n", encoding="utf-8")
        root = self.checkout("main", {"LITELLM_MASTER_KEY": "sk-stack-master-0123456789"},
                             {"permissions": {"allow": ["Bash(curl -H 'Authorization: Bearer sk-stack-master-0123456789' *)"]}})
        (result,) = ca.connect([root], env_file=env)
        self.assertTrue(result[1].startswith("updated; a stack key is still written elsewhere"), result[1])
        doc = json.loads(ca.settings_file(root).read_text(encoding="utf-8"))
        self.assertNotIn("LITELLM_MASTER_KEY", doc["env"])
        self.assertEqual(len(doc["permissions"]["allow"]), 1)      # left for the owner
        self.assertEqual(ca.holders([root], env_file=env)["stack"], [ca.settings_file(root)])

    def test_a_file_changed_during_the_update_is_read_again(self):
        env = self.dir / ".env"
        root = self.checkout("main", dict(STACK))
        path = ca.settings_file(root)
        real = ca.write_json
        calls = []

        def racing(target, doc, expect=None):
            if not calls:   # a Claude Code session saves an allow rule between our read and our write
                target.write_text(json.dumps({"env": dict(STACK), "permissions": {"allow": ["Bash(ls)"]}}),
                                  encoding="utf-8")
            calls.append(1)
            return real(target, doc, expect)

        with mock.patch.object(ca, "write_json", side_effect=racing):
            (result,) = ca.connect([root], env_file=env)
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(result[1], "updated")
        self.assertEqual(len(calls), 2)
        self.assertEqual(doc["permissions"]["allow"], ["Bash(ls)"])   # the session's rule survived
        self.assertNotIn("LITELLM_MASTER_KEY", doc["env"])
        self.assertEqual([f.name for f in path.parent.iterdir()], [path.name])   # no temporary file left

    def test_a_broken_settings_file_is_reported_not_overwritten(self):
        root = self.checkout("main", {})
        ca.settings_file(root).write_text("{oops", encoding="utf-8")
        (result,) = ca.connect([root], env_file=self.dir / ".env")
        self.assertTrue(result[1].startswith("failed"))
        self.assertEqual(ca.settings_file(root).read_text(encoding="utf-8"), "{oops")

    def test_holders_and_status(self):
        env = self.dir / ".env"
        old = self.checkout("old", dict(STACK))
        new = self.checkout("new", {})
        ca.connect([new], env_file=env)
        held = ca.holders([old, new])
        self.assertEqual((held["stack"], held["claude"]), ([ca.settings_file(old)], [ca.settings_file(new)]))
        with mock.patch.object(ca, "stack_env_file", return_value=env), \
                mock.patch.object(ca, "checkouts", return_value=[old, new]):
            st = ca.status(self.profile(enabled=False))
        self.assertEqual((st["enabled"], st["keys"], st["checkouts"]), (False, True, 2))

    def test_checkouts_follow_git_worktrees(self):
        out = "worktree C:/x/main\nHEAD abc\n\nworktree C:/x/main/.claude/worktrees/w1\nHEAD def\n"
        fake = types.SimpleNamespace(stdout=out)
        with mock.patch.object(ca.subprocess, "run", return_value=fake), \
                mock.patch.object(Path, "is_dir", return_value=True), \
                mock.patch("stacklib.deploy.is_app", return_value=False):
            roots = ca.checkouts()
        self.assertEqual([r.as_posix() for r in roots], ["C:/x/main", "C:/x/main/.claude/worktrees/w1"])

    def test_the_installed_app_knows_no_checkout(self):
        # The app keeps no path back to its checkout (test_deploy); the checkout connects Claude Code when it installs.
        with mock.patch("stacklib.deploy.is_app", return_value=True), \
                mock.patch.object(ca.subprocess, "run", side_effect=AssertionError("no git in the app")):
            self.assertEqual(ca.checkouts(), [])


class ClaudeCodeSettingsTests(TempDir):
    def test_profile_b_uses_claudes_gateway_key(self):
        prof = {"claude_code": {"local_profile": {}}, "ports": {"litellm": 4000}, "models": {"primary_num_ctx": 32768}}
        with mock.patch.object(ca, "read_keys", return_value={ca.GATEWAY_KEY: "sk-claude-x", ca.TOOLS_KEY: "b"}),                 mock.patch.object(ca, "ensure_keys", side_effect=AssertionError("claude-env must not write keys")):
            env = claude_env.local_profile_env(prof)
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "sk-claude-x")

    def test_profile_b_without_claudes_key_stops_with_the_fix(self):
        prof = {"claude_code": {"local_profile": {}}, "ports": {"litellm": 4000}, "models": {"primary_num_ctx": 32768}}
        with mock.patch.object(ca, "read_keys", return_value={ca.GATEWAY_KEY: "", ca.TOOLS_KEY: ""}),                 mock.patch.object(ca, "stack_env_file", return_value=self.dir / ".env"),                 self.assertRaises(SystemExit):
            claude_env.local_profile_env(prof)
        self.assertFalse((self.dir / ".env").exists())

    def test_settings_local_gets_claudes_keys_not_the_stacks(self):
        (self.dir / ".claude").mkdir()
        p = self.dir / ".claude" / "settings.local.json"
        p.write_text(json.dumps({"env": dict(STACK)}), encoding="utf-8")
        keys = {ca.GATEWAY_KEY: "sk-claude-x", ca.TOOLS_KEY: "b"}
        with mock.patch.object(claude_env, "REPO", self.dir), mock.patch.object(ca, "ensure_keys", return_value=keys):
            claude_env.write_settings_local({})
        doc = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(doc["env"], keys)
        self.assertEqual(doc["enabledMcpjsonServers"], ["orchestrator"])

    def test_mcp_json_reads_claudes_bearer(self):
        mcp = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))
        header = mcp["mcpServers"]["orchestrator"]["headers"]["Authorization"]
        self.assertEqual(header, "Bearer ${" + ca.TOOLS_KEY + "}")
        self.assertFalse(ca.TOOLS_KEY.endswith(("_TOKEN", "_API_KEY")))   # Claude Code blanks those in .mcp.json


class WiringTests(TempDir):
    def test_gateway_config_names_the_custom_auth(self):
        import yaml

        source = (REPO / "scripts" / "stacklib" / "litellm_build.py").read_text(encoding="utf-8")
        self.assertIn('"custom_auth": "custom_auth.user_api_key_auth"', source)
        generated = yaml.safe_load((REPO / "infrastructure" / "litellm" / "config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(generated["general_settings"]["custom_auth"], "custom_auth.user_api_key_auth")
        # without this, a custom_auth makes LiteLLM skip its common checks for every key, the master key included
        self.assertIs(generated["general_settings"]["custom_auth_run_common_checks"], True)
        self.assertTrue((REPO / "infrastructure" / "litellm" / "custom_auth.py").exists())

    def test_services_get_the_key_and_the_switch(self):
        prof = self.profile(enabled=False)
        prof.update({"ports": {"litellm": 4000, "orchestrator": 8765, "phoenix": 6006, "phoenix_grpc": 4317,
                               "open_webui": 3000}, "observability": {"phoenix": False}, "services": {}})
        dotenv = {**STACK, ca.GATEWAY_KEY: "sk-claude-x", ca.TOOLS_KEY: "b"}
        with mock.patch.object(services, "load_dotenv", return_value=dotenv), \
                mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch.object(services, "tool_command", return_value=["litellm"]), \
                mock.patch.object(services, "gateway_label_env", return_value={}), \
                mock.patch("stacklib.media.service_command", return_value=None), \
                mock.patch("stacklib.dictation.service_command", return_value=None):
            for k in (*ca.CLAUDE_KEYS, ca.FILE_ENV, ca.START_ENV):
                os.environ.pop(k, None)
            cmds = services.commands(prof)
        gw, tools = cmds["litellm"]["env"], cmds["orchestrator"]["env"]
        self.assertEqual((gw[ca.GATEWAY_KEY], gw[ca.START_ENV]), ("sk-claude-x", "0"))
        self.assertEqual((tools[ca.TOOLS_KEY], tools[ca.START_ENV]), ("b", "0"))
        self.assertEqual(gw[ca.FILE_ENV], str(self.dir / ".run" / ca.SWITCH_NAME))

    def test_setting_applies_without_a_restart(self):
        setting = next(s for s in settings.SETTINGS if settings.setting_id(s) == "claude_access.enabled")
        self.assertEqual((setting.kind, setting.effect), ("bool", "claude"))
        self.assertIn("claude", settings.EFFECT_TEXT)
        new = {**self.profile(enabled=False), "services": {}}
        with mock.patch.object(settings, "save", return_value=[setting]), \
                mock.patch.object(settings.prof, "resolve_profile", return_value=new), \
                mock.patch.object(settings.services, "_task_managed", return_value=set()), \
                mock.patch.object(settings.services, "stop") as stop, \
                mock.patch.object(settings.services, "start") as start:
            settings.apply({"name": "T"}, {"claude_access.enabled": False}, log=lambda m: None)
        stop.assert_not_called()
        start.assert_not_called()
        self.assertFalse(ca.Switch(ca.switch_path(new)).on())

    def test_current_values_reads_the_switch(self):
        base = {"models": {}, "observability": {}, "services": {}, "ollama_env": {}}
        self.assertTrue(settings.current_values(base)["claude_access.enabled"])
        self.assertFalse(settings.current_values({**base, "claude_access": {"enabled": False}})["claude_access.enabled"])

    def test_usage_names_claude_by_its_key(self):
        self.assertEqual(usage.client_of({"key_alias": "claude", "user_agent": "claude-cli/2.1 (external)"}), "Claude Code")
        self.assertEqual(usage.client_of({"key_alias": "claude", "user_agent": "agent-stack-retro"}), "Claude")
        self.assertEqual(usage.client_of({"user_agent": "agent-stack-retro"}), usage.COMPONENTS.get("retro", "retro"))


# ---------------------------------------------------------------- the gateway's custom auth, with LiteLLM stubbed

class _ProxyException(Exception):
    def __init__(self, message, type, param, code=None):  # noqa: A002 - LiteLLM's signature
        super().__init__(message)
        self.message, self.type, self.param, self.code = message, type, param, str(code)


class _UserAPIKeyAuth:
    def __init__(self, **kw):
        self.__dict__.update(kw)


LLM_ROUTES = {"/v1/messages", "/v1/chat/completions", "/chat/completions", "/v1/models", "/v1/messages/count_tokens"}


def _litellm_stubs() -> dict:
    names = ("litellm", "litellm.proxy", "litellm.proxy._types", "litellm.proxy.auth", "litellm.proxy.auth.auth_utils",
             "litellm.proxy.auth.route_checks")
    mods = {n: types.ModuleType(n) for n in names}
    mods["litellm.proxy._types"].ProxyException = _ProxyException
    mods["litellm.proxy._types"].UserAPIKeyAuth = _UserAPIKeyAuth
    mods["litellm.proxy._types"].LitellmUserRoles = types.SimpleNamespace(INTERNAL_USER="internal_user")
    mods["litellm.proxy.auth.auth_utils"].get_request_route = lambda request: request.route
    mods["litellm.proxy.auth.route_checks"].RouteChecks = types.SimpleNamespace(
        is_llm_api_route=lambda route: route in LLM_ROUTES)
    return mods


class GatewayAuthTests(TempDir):
    def setUp(self):
        super().setUp()
        self.mods = mock.patch.dict(sys.modules, _litellm_stubs())
        self.mods.start()
        import custom_auth

        self.auth = custom_auth
        self.env = mock.patch.dict(os.environ, {ca.GATEWAY_KEY: "sk-claude-x"})
        self.env.start()
        self.path = ca.write_switch(self.profile(enabled=True))
        self.switch = mock.patch.object(custom_auth, "SWITCH", ca.Switch(self.path))
        self.switch.start()

    def tearDown(self):
        self.switch.stop()
        self.env.stop()
        self.mods.stop()
        super().tearDown()

    def call(self, key, route="/v1/messages"):
        return run(self.auth.user_api_key_auth(types.SimpleNamespace(route=route), key))

    def test_other_keys_go_on_to_litellms_own_check(self):
        for key in ("sk-stack-master", "", None, "sk-claude-y"):
            self.assertIsNone(self.call(key))

    def test_no_claude_key_configured_lets_nothing_through_as_claude(self):
        with mock.patch.dict(os.environ, {ca.GATEWAY_KEY: ""}):
            self.assertIsNone(self.call(""))

    def test_the_master_key_is_never_claudes_even_if_they_match(self):
        with mock.patch.dict(os.environ, {ca.GATEWAY_KEY: "sk-same", "LITELLM_MASTER_KEY": "sk-same"}):
            ca.write_switch(self.profile(enabled=False))
            self.assertIsNone(self.call("sk-same"))          # LiteLLM's own check decides, as for the master key

    def test_claudes_key_works_for_model_calls_while_on(self):
        for route in ("/v1/messages", "/v1/models", "/v1/chat/completions"):
            got = self.call("sk-claude-x", route)
            self.assertEqual((got.key_alias, got.user_id), (ca.ALIAS, ca.ALIAS))

    def test_claudes_key_is_refused_when_off_at_the_next_request(self):
        self.assertIsNotNone(self.call("sk-claude-x"))
        ca.write_switch(self.profile(enabled=False))
        with self.assertRaises(_ProxyException) as e:
            self.call("sk-claude-x")
        self.assertEqual(e.exception.code, "403")
        self.assertIn("turned off", e.exception.message)
        self.assertIsNone(self.call("sk-stack-master"))      # the stack's own key is untouched

    def test_claudes_key_is_refused_outside_model_calls(self):
        # LiteLLM's own "LLM route" test admits several of these (pass-through, traces, RAG, files): the list is ours
        for route in ("/model/new", "/config/update", "/key/generate", "/health", "/ui", "/v1/traces", "/rag/query",
                      "/anthropic/v1/messages", "/openai/v1/chat/completions", "/v1/files", "/mcp", "/a2a/x"):
            with self.assertRaises(_ProxyException) as e:
                self.call("sk-claude-x", route)
            self.assertEqual(e.exception.code, "403", route)


# ---------------------------------------------------------------- the agent tools' bearers (fastmcp is a project dependency)

class AgentToolsAuthTests(TempDir):
    def setUp(self):
        super().setUp()
        from orchestrator.access import StackTokenVerifier

        self.path = ca.write_switch(self.profile(enabled=True))
        self.verifier = StackTokenVerifier("stack-bearer", "claude-bearer", ca.Switch(self.path))

    def check(self, token):
        found = run(self.verifier.verify_token(token))
        return found.client_id if found else None

    def test_both_bearers_while_on(self):
        self.assertEqual(self.check("stack-bearer"), "local-stack")
        self.assertEqual(self.check("claude-bearer"), ca.ALIAS)
        self.assertIsNone(self.check("other"))

    def test_off_refuses_only_claude(self):
        ca.write_switch(self.profile(enabled=False))
        self.assertIsNone(self.check("claude-bearer"))
        self.assertEqual(self.check("stack-bearer"), "local-stack")
        time.sleep(0.01)
        ca.write_switch(self.profile(enabled=True))
        self.assertEqual(self.check("claude-bearer"), ca.ALIAS)

    def test_claude_bearer_equal_to_the_stacks_stays_the_stacks(self):
        from orchestrator.access import StackTokenVerifier

        v = StackTokenVerifier("same", "same", ca.Switch(self.path))
        found = run(v.verify_token("same"))
        self.assertEqual(found.client_id, "local-stack")


if __name__ == "__main__":
    unittest.main()
