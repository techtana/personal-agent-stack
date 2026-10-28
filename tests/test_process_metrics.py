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


class ProcessSampling(unittest.TestCase):
    def test_cpu_is_unavailable_until_a_baseline_sample_exists(self):
        process = mock.Mock()
        process.pid = 42
        process.is_running.return_value = True
        process.cpu_percent.side_effect = [0.0, 12.5]
        process.memory_info.return_value = SimpleNamespace(rss=1024 * 1024)
        process.name.return_value = "worker.exe"
        sampler = process_metrics.ProcessSampler()
        with (
            mock.patch.object(process_metrics.psutil, "process_iter", return_value=[process]),
            mock.patch.object(process_metrics, "_gpu_usage", return_value={}),
        ):
            first = sampler.sample()
            second = sampler.sample()

        self.assertIsNone(first[0]["cpu_percent"])
        self.assertEqual(second[0]["cpu_percent"], 12.5)
        self.assertEqual(second[0]["memory_mb"], 1)


if __name__ == "__main__":
    unittest.main()
