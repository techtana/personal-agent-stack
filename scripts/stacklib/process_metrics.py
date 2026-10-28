"""Current per-process CPU, memory and GPU utilization for the tray."""
from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any

import psutil

from . import IS_WINDOWS, warn, which

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
    except (OSError, subprocess.SubprocessError) as exc:
        warn(f"per-process GPU counters unavailable: {exc}")
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        warn(f"could not parse Windows GPU counters: {exc}")
        return {}
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
        warn(f"per-process NVIDIA GPU metrics unavailable: {exc}")
        return {}
    return parse_nvidia_pmon(result.stdout)


def _gpu_usage() -> dict[int, dict[str, float]]:
    return _windows_gpu_usage() if IS_WINDOWS else _nvidia_gpu_usage()


class ProcessSampler:
    """Sample all visible processes, retaining psutil counters between tray refreshes."""

    def __init__(self) -> None:
        self._processes: dict[int, psutil.Process] = {}

    def sample(self) -> list[dict[str, Any]]:
        gpu = _gpu_usage()
        rows = []
        live: dict[int, psutil.Process] = {}
        for process in psutil.process_iter():
            try:
                pid = process.pid
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
                    "cpu_percent": None if is_new else cpu_percent,
                    "memory_mb": memory_mb,
                    "gpu_percent": gpu_metrics.get("gpu_percent"),
                    "gpu_memory_mb": gpu_metrics.get("gpu_memory_mb"),
                }
            )
        self._processes = live
        return sorted(
            rows,
            key=lambda row: (
                row["gpu_percent"] or 0,
                row["cpu_percent"] or 0,
                row["memory_mb"],
            ),
            reverse=True,
        )
