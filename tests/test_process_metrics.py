from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import process_metrics
from stacklib.process_metrics import parse_nvidia_pmon, parse_windows_gpu_counters  # noqa: E402


class WindowsGpuCounters(unittest.TestCase):
    def test_aggregates_per_process_engine_usage_and_dedicated_memory(self):
        rows = [
            {
                "path": r"\GPU Engine(pid_123_luid_0x0_phys_0_eng_0_engtype_3d)\Utilization Percentage",
                "value": 35.5,
            },
            {
                "path": r"\GPU Engine(pid_123_luid_0x0_phys_0_eng_1_engtype_compute)\Utilization Percentage",
                "value": 80,
            },
            {
                "path": r"\GPU Process Memory(pid_123_luid_0x0_phys_0)\Dedicated Usage",
                "value": 1048576,
            },
            {
                "path": r"\GPU Engine(pid_456_luid_0x0_phys_0_eng_0_engtype_3d)\Utilization Percentage",
                "value": 10,
            },
            {"path": "not a process counter", "value": 90},
        ]

        result = parse_windows_gpu_counters(rows)

        self.assertEqual(result[123]["gpu_percent"], 100)
        self.assertEqual(result[123]["gpu_memory_mb"], 1)
        self.assertEqual(result[456]["gpu_percent"], 10)


class NvidiaPmon(unittest.TestCase):
    def test_parses_process_gpu_utilization_and_ignores_unavailable_values(self):
        output = """# gpu         pid   type     sm    mem    enc    dec    jpg    ofa    command
0 37364 C 42 18 - - - - llama-server
0 2820 C+G - - - - - - chrome.exe
"""

        self.assertEqual(parse_nvidia_pmon(output), {37364: {"gpu_percent": 42.0}})


def _process(pid: int, cpu: list[float], name: str = "worker.exe") -> mock.Mock:
    process = mock.Mock()
    process.pid = pid
    process.is_running.return_value = True
    process.cpu_percent.side_effect = cpu
    process.memory_info.return_value = SimpleNamespace(rss=1024 * 1024)
    process.name.return_value = name
    return process


class ProcessSampling(unittest.TestCase):
    def setUp(self):
        # A fake clock: sleeping advances it, so priming's minimum CPU window costs no real time.
        self.now = 0.0
        clock = SimpleNamespace(monotonic=lambda: self.now, sleep=self._sleep)
        for p in (
            mock.patch.object(process_metrics, "time", clock),
            mock.patch.object(process_metrics, "CPU_COUNT", 4),
            mock.patch.object(process_metrics, "_gpu_usage", return_value={}),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _sleep(self, seconds: float) -> None:
        self.now += seconds

    def _sample(self, sampler, *walks):
        with mock.patch.object(process_metrics.psutil, "process_iter", side_effect=[list(w) for w in walks]):
            return sampler.sample()

    def test_first_sample_primes_a_baseline_and_shares_cpu_over_all_processors(self):
        process = _process(42, [0.0, 50.0])  # priming call, then 50% of one core since priming
        rows = self._sample(process_metrics.ProcessSampler(), [process], [process])

        self.assertEqual(rows[0]["cpu_percent"], 12.5)  # 50% of one core out of 4 logical processors
        self.assertEqual(rows[0]["memory_mb"], 1)
        self.assertGreaterEqual(self.now, process_metrics.CPU_MIN_WINDOW_SECONDS)  # measured over at least the window

    def test_cpu_is_unavailable_for_a_process_that_started_after_the_baseline(self):
        old, new = _process(42, [0.0, 20.0]), _process(43, [0.0], "late.exe")
        rows = {r["pid"]: r for r in self._sample(process_metrics.ProcessSampler(), [old], [old, new])}

        self.assertEqual(rows[42]["cpu_percent"], 5.0)
        self.assertIsNone(rows[43]["cpu_percent"])

    def test_the_idle_process_is_never_listed(self):
        idle, worker = _process(0, [0.0, 1100.0], "System Idle Process"), _process(42, [0.0, 4.0])
        rows = self._sample(process_metrics.ProcessSampler(), [idle, worker], [idle, worker])

        self.assertEqual([r["pid"] for r in rows], [42])
        idle.cpu_percent.assert_not_called()

    def test_a_stale_baseline_is_primed_again(self):
        process = _process(42, [0.0, 8.0, 12.0, 0.0, 40.0])
        sampler = process_metrics.ProcessSampler()
        self._sample(sampler, [process], [process])  # primes, then walks
        self.now += 10
        fresh = self._sample(sampler, [process])  # baseline 10 s old: one walk, no priming
        self.now += process_metrics.BASELINE_MAX_AGE_SECONDS + 60
        stale = self._sample(sampler, [process], [process])  # minutes old: primed again first

        self.assertEqual(fresh[0]["cpu_percent"], 3.0)
        self.assertEqual(stale[0]["cpu_percent"], 10.0)  # measured since the new baseline, not over 70 s
        self.assertEqual(process.cpu_percent.call_count, 5)


if __name__ == "__main__":
    unittest.main()
