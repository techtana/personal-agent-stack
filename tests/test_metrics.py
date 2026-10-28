from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import metrics  # noqa: E402


class MetricAggregation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def write_rows(self, rows: list[dict]) -> None:
        path = self.directory / "today.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def test_groups_model_process_totals_and_averages_for_selected_period(self):
        self.write_rows(
            [
                {
                    "ts": "2026-10-26T11:00:00+00:00",
                    "process": "ollama",
                    "model": "ollama_chat/qwen3.5:9b",
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "cost": 0,
                    "model_load_ms": 100,
                    "input_ms": 200,
                    "inference_ms": 400,
                    "model_total_ms": 700,
                    "latency_ms": 900,
                },
                {
                    "ts": "2026-10-26T11:30:00+00:00",
                    "process": "ollama",
                    "model": "ollama_chat/qwen3.5:9b",
                    "prompt_tokens": 20,
                    "completion_tokens": 6,
                    "cost": 0,
                    "model_load_ms": 300,
                    "input_ms": 400,
                    "inference_ms": 800,
                    "model_total_ms": 1300,
                    "latency_ms": 1900,
                },
                {
                    "ts": "2026-10-26T09:00:00+00:00",
                    "process": "anthropic",
                    "model": "claude-haiku-5-5",
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "cost": 0.0001,
                    "latency_ms": 1500,
                },
            ]
        )

        rows = metrics.summarize(self.directory, "1 hour", now=self.now)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["process"], "ollama")
        self.assertEqual(rows[0]["model"], "qwen3.5:9b")
        self.assertEqual(rows[0]["requests"], 2)
        self.assertEqual(rows[0]["prompt_tokens"], 30)
        self.assertEqual(rows[0]["completion_tokens"], 10)
        self.assertEqual(rows[0]["cost_usd"], 0)
        self.assertEqual(rows[0]["avg_model_load_ms"], 200)
        self.assertEqual(rows[0]["avg_input_ms"], 300)
        self.assertEqual(rows[0]["avg_inference_ms"], 600)
        self.assertEqual(rows[0]["avg_model_total_ms"], 1000)
        self.assertEqual(rows[0]["avg_latency_ms"], 1400)

    def test_all_time_includes_cloud_cost_and_keeps_unknown_phase_unavailable(self):
        self.write_rows(
            [
                {
                    "ts": "2026-10-24T10:00:00+00:00",
                    "provider": "anthropic",
                    "model": "claude-haiku-5-5",
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "cost": 0.0001,
                    "latency_ms": 1500,
                },
                "{bad json}\n",
            ]
        )

        rows = metrics.summarize(self.directory, "All time", now=self.now)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["process"], "anthropic")
        self.assertEqual(rows[0]["prompt_tokens"], 100)
        self.assertEqual(rows[0]["completion_tokens"], 50)
        self.assertAlmostEqual(rows[0]["cost_usd"], 0.0001)
        self.assertIsNone(rows[0]["avg_input_ms"])
        self.assertEqual(rows[0]["avg_latency_ms"], 1500)

    def test_rejects_unknown_period(self):
        with self.assertRaises(ValueError):
            metrics.summarize(self.directory, "forever", now=self.now)


if __name__ == "__main__":
    unittest.main()
