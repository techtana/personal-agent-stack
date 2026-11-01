"""Current per-process CPU, memory and GPU utilization for the tray."""
from __future__ import annotations

import json
import re
import subprocess
import time
from typing import Any

import psutil

from . import IS_WINDOWS, warn, which

GPU_RETRY_MAX_SECONDS = 300
CPU_COUNT = psutil.cpu_count() or 1  # logical processors; CPU % is a share of all of them, as in Task Manager
BASELINE_MAX_AGE_SECONDS = 30  # an older CPU baseline is taken again, so no value averages over minutes
CPU_MIN_WINDOW_SECONDS = 1.0  # shortest span a CPU value is measured over; process CPU times tick every ~16 ms


class GpuUnavailable(RuntimeError):
    """The per-process GPU counters could not be read this time."""

_GPU_COUNTER_SCRIPT = (
    "$c=Get-Counter -Counter '\\GPU Engine(*)\\Utilization Percentage',"
    "'\\GPU Process Memory(*)\\Dedicated Usage' -SampleInterval 1 -MaxSamples 1 -ErrorAction Stop; "
    "$rows=@($c.CounterSamples | ForEach-Object { @{path=$_.Path; value=$_.CookedValue} }); "
    "ConvertTo-Json -InputObject $rows -Compress"
)


def parse_windows_gpu_counters(rows: list[dict[str, Any]]) -> dict[int, dict[str, float]]:
    """Aggregate Windows GPU Engine utilization and dedicated memory by PID."""
    result: dict[int, dict[str, float]] = {}
    for row in rows:
        path = str(row.get("path") or "")
        match = re.search(r"pid_(\d+)_", path, re.IGNORECASE)
        if match is None:
            continue
        try:
            value = float(row["value"])
        except (KeyError, TypeError, ValueError):
            continue
        if value < 0:
            continue
        pid = int(match.group(1))
        record = result.setdefault(pid, {})
        if "utilization percentage" in path.lower():
            record["gpu_percent"] = record.get("gpu_percent", 0.0) + value
        elif "dedicated usage" in path.lower():
            record["gpu_memory_mb"] = record.get("gpu_memory_mb", 0.0) + value / (1024 * 1024)
    for record in result.values():
        if "gpu_percent" in record:
            record["gpu_percent"] = min(100.0, record["gpu_percent"])
    return result


def parse_nvidia_pmon(output: str) -> dict[int, dict[str, float]]:
    """Parse nvidia-smi process monitor output where the driver exposes utilization."""
    result: dict[int, dict[str, float]] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 5 or not fields[0].isdigit() or not fields[1].isdigit():
            continue
        try:
            utilization = float(fields[3])
        except ValueError:
            continue
        if utilization >= 0:
            result[int(fields[1])] = {"gpu_percent": utilization}
    return result


def _windows_gpu_usage() -> dict[int, dict[str, float]]:
    command = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        _GPU_COUNTER_SCRIPT,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=8,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip().splitlines()
        raise GpuUnavailable(f"Get-Counter exited with code {exc.returncode}" + (f" ({detail[0][:160]})" if detail else "")) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise GpuUnavailable(f"Windows GPU counters unavailable: {exc}") from exc
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GpuUnavailable(f"could not parse Windows GPU counters: {exc}") from exc
    if not isinstance(data, list):
        return {}
    return parse_windows_gpu_counters(data)


def _nvidia_gpu_usage() -> dict[int, dict[str, float]]:
    nvidia_smi = which("nvidia-smi")
    if not nvidia_smi:
        return {}
    try:
        result = subprocess.run(
            [nvidia_smi, "pmon", "-c", "1"],
            capture_output=True,
            text=True,
            timeout=8,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GpuUnavailable(f"NVIDIA process metrics unavailable: {exc}") from exc
    return parse_nvidia_pmon(result.stdout)


def _gpu_usage() -> dict[int, dict[str, float]]:
    return _windows_gpu_usage() if IS_WINDOWS else _nvidia_gpu_usage()


class ProcessSampler:
    """Sample all visible processes, retaining psutil counters between samples."""

    def __init__(self) -> None:
        self._processes: dict[int, psutil.Process] = {}
        self._sampled_at: float | None = None  # monotonic time of the walk that set the current CPU baseline
        self._gpu_failures = 0
        self._gpu_retry_at = 0.0
        self.gpu_problem = ""  # why the GPU columns are empty, for the window

    def _gpu(self) -> dict[int, dict[str, float]]:
        """GPU counters, skipped for a while after a failure (15 s, doubling up to 5 min): each try starts PowerShell
        or nvidia-smi and can take up to 8 s."""
        if time.monotonic() < self._gpu_retry_at:
            return {}
        try:
            gpu = _gpu_usage()
        except GpuUnavailable as exc:
            self._gpu_failures += 1
            wait = min(GPU_RETRY_MAX_SECONDS, 15 * 2 ** (self._gpu_failures - 1))
            self._gpu_retry_at = time.monotonic() + wait
            self.gpu_problem = f"{exc}; next try in {wait} s"
            warn(self.gpu_problem)
            return {}
        self._gpu_failures, self.gpu_problem = 0, ""
        return gpu

    def _prime(self) -> None:
        """Take a fresh CPU baseline for every process; the next walk measures CPU from here."""
        primed: dict[int, psutil.Process] = {}
        for process in psutil.process_iter():
            if process.pid == 0:  # System Idle Process (Windows), kernel_task (macOS): idle time, not a process
                continue
            try:
                process.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            primed[process.pid] = process
        self._processes = primed

    def sample(self) -> list[dict[str, Any]]:
        """One row per process. CPU is the share of all logical processors (100 = the whole machine), measured since
        the previous sample; a missing or stale baseline is primed first, so the first sample already has values."""
        primed_at = None
        if self._sampled_at is None or time.monotonic() - self._sampled_at > BASELINE_MAX_AGE_SECONDS:
            self._prime()
            primed_at = time.monotonic()
        gpu = self._gpu()
        if primed_at is not None:  # the GPU counters were skipped or quick: give the CPU baseline a usable span
            time.sleep(max(0.0, CPU_MIN_WINDOW_SECONDS - (time.monotonic() - primed_at)))
        rows = []
        live: dict[int, psutil.Process] = {}
        for process in psutil.process_iter():
            try:
                pid = process.pid
                if pid == 0:
                    continue
                current = self._processes.get(pid)
                is_new = current is None or not current.is_running()
                if is_new:
                    current = process
                cpu_percent = current.cpu_percent(interval=None)
                memory_mb = current.memory_info().rss / (1024 * 1024)
                name = current.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            live[pid] = current
            gpu_metrics = gpu.get(pid, {})
            rows.append(
                {
                    "pid": pid,
                    "name": name,
                    "cpu_percent": None if is_new else cpu_percent / CPU_COUNT,
                    "memory_mb": memory_mb,
                    "gpu_percent": gpu_metrics.get("gpu_percent"),
                    "gpu_memory_mb": gpu_metrics.get("gpu_memory_mb"),
                }
            )
        self._processes = live
        self._sampled_at = time.monotonic()
        return sorted(
            rows,
            key=lambda row: (
                row["gpu_percent"] or 0,
                row["cpu_percent"] or 0,
                row["memory_mb"],
            ),
            reverse=True,
        )
