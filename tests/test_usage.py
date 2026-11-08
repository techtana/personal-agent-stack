from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import usage  # noqa: E402

NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")
OWUI = "Python/3.11 aiohttp/3.14.3"


def row(**kw) -> dict:
    base = {"ts": NOW, "status": "success", "requested_model": "local-primary", "model": "ollama_chat/qwen3.5:9b",
            "prompt_tokens": 100, "completion_tokens": 0, "latency_ms": 0, "user_agent": OWUI}
    base.update(kw)
    return base


ROWS = [
    # Two replies Ollama timed: 1000 tokens in 20 s of generation each, 22 s on the wall clock.
    row(completion_tokens=1000, latency_ms=22000, model_load_ms=1000, input_ms=500, inference_ms=20000),
    row(completion_tokens=1000, latency_ms=22000, model_load_ms=1000, input_ms=500, inference_ms=20000),
    # A background call with no Ollama timings that waited in the queue: 100 tokens in 50 s.
    row(prompt_tokens=7000, completion_tokens=100, latency_ms=50000),
    # Another client on another alias.
    row(requested_model="app-dev", user_agent="claude-cli/2.1.302", completion_tokens=500, latency_ms=10000,
        inference_ms=9000),
]


class Summary(unittest.TestCase):
    def summarize(self, group_by="alias"):
        with mock.patch.object(usage.traces, "litellm_rows", return_value=ROWS),                 mock.patch.object(usage.traces, "usage_rows", return_value=[]):
            return usage.summarize(1, group_by)

    def test_keeps_every_request_and_splits_decode_from_end_to_end_speed(self):
        lp = next(m for m in self.summarize()["models"] if m["model"] == "local-primary")
        self.assertEqual(lp["requests"], 3)
        self.assertEqual(lp["timed"], 2)
        self.assertAlmostEqual(lp["decode_tok_s"], 50.0)  # 2000 tokens / 40 s of Ollama generation
        self.assertAlmostEqual(lp["e2e_tok_s"], 2100 / 94)  # all output over all wall-clock time
        self.assertEqual(lp["breakdown_ms"], {"load": 1000, "prompt": 500, "generate": 20000, "other": 500})
        self.assertEqual(lp["untimed_avg_ms"], 50000)

    def test_rows_split_by_client_and_totals_cover_everything(self):
        data = self.summarize()
        lp = next(m for m in data["models"] if m["model"] == "local-primary")
        self.assertEqual([(c["model"], c["requests"]) for c in lp["clients"]], [("Open WebUI", 3)])
        self.assertEqual(data["totals"]["requests"], 4)
        self.assertEqual(data["sub_by"], "client")

    def test_group_by_client_splits_by_alias(self):
        data = self.summarize("client")
        names = {m["model"]: [c["model"] for c in m["clients"]] for m in data["models"]}
        self.assertEqual(names, {"Open WebUI": ["local-primary"], "Claude Code": ["app-dev"]})
        self.assertEqual(data["sub_by"], "alias")

    def test_client_names(self):
        self.assertEqual(usage.client_of({"user_agent": OWUI}), "Open WebUI")
        self.assertEqual(usage.client_of({"user_agent": "Python-urllib/3.12"}), "Stack scripts")
        self.assertEqual(usage.client_of({"user_agent": "python-httpx/0.28.1"}), "Orchestrator")
        self.assertEqual(usage.client_of({}), "Unknown")

    def test_breakdown_text_names_ollama_and_untimed_parts(self):
        lp = next(m for m in self.summarize()["models"] if m["model"] == "local-primary")
        text = usage.breakdown_text(lp, "local-primary")
        self.assertIn("2 timed by Ollama", text)
        self.assertIn("20.0 s generate", text)
        self.assertIn("1 without Ollama timings, 50.0 s each", text)


if __name__ == "__main__":
    unittest.main()
