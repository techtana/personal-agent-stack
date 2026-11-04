"""Tests for the primary-model warm-up (scripts/stacklib/ollama.py) and the gateway keep-alive it relies on.

Run with `uv run python -m unittest discover -s tests`.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import yaml  # noqa: E402

from stacklib import litellm_build, ollama  # noqa: E402


def _profile(**models) -> dict:
    m = {"fim": "fim:1b", "embed": "embed", "small": "qwen3.5:9b", "primary": "qwen3.5:9b", "reviewer": None,
         "primary_num_ctx": 32768, "small_num_ctx": 32768, "primary_options": {}, "reviewer_options": {}}
    m.update(models)
    return {"name": "TEST", "hardware_class": "test", "models": m, "ports": {"ollama": 11434},
            "policy": {"external": {"enabled": False}, "location": "onprem"}, "observability": {}}


class WarmPrimaryTest(unittest.TestCase):
    def test_loads_primary_with_gateway_options_and_no_keep_alive(self) -> None:
        p = _profile(primary="big:35b", primary_options={"use_mmap": True})
        with mock.patch.object(ollama, "version", return_value="0.40"), mock.patch.object(ollama, "api") as api:
            msg = ollama.warm_primary(p)
        path, payload = api.call_args.args[1], api.call_args.args[2]
        self.assertEqual(path, "/api/generate")
        self.assertEqual(payload["model"], "big:35b")
        self.assertEqual(payload["options"], {"num_ctx": 32768, "use_mmap": True})
        self.assertNotIn("keep_alive", payload)
        self.assertNotIn("prompt", payload)
        self.assertIn("warmed big:35b", msg)

    def test_falls_back_to_small_model(self) -> None:
        p = _profile(primary=None, small="small:9b", small_num_ctx=16384, primary_options={"use_mmap": True})
        with mock.patch.object(ollama, "version", return_value="0.40"), mock.patch.object(ollama, "api") as api:
            ollama.warm_primary(p)
        self.assertEqual(api.call_args.args[2]["options"], {"num_ctx": 16384})

    def test_skips_when_ollama_is_down(self) -> None:
        with mock.patch.object(ollama, "version", return_value=None), mock.patch.object(ollama, "api") as api:
            msg = ollama.warm_primary(_profile())
        api.assert_not_called()
        self.assertIn("not answering", msg)

    def test_reports_a_failed_load(self) -> None:
        with mock.patch.object(ollama, "version", return_value="0.40"), \
                mock.patch.object(ollama, "api", side_effect=OSError("timed out")):
            self.assertIn("failed: timed out", ollama.warm_primary(_profile()))


class GatewayKeepAliveTest(unittest.TestCase):
    def test_chat_deployments_leave_keep_alive_to_ollama(self) -> None:
        # Ollama keeps the last request's keep_alive, so any per-alias value would override OLLAMA_KEEP_ALIVE for
        # the runner every alias shares.
        cfg = yaml.safe_load(litellm_build.build_config(_profile()))
        chat = [d for d in cfg["model_list"] if d["litellm_params"].get("model", "").startswith("ollama_chat/qwen3.5:9b")]
        self.assertGreater(len(chat), 2)
        for d in chat:
            self.assertNotIn("keep_alive", d["litellm_params"], d["model_name"])


if __name__ == "__main__":
    unittest.main()
