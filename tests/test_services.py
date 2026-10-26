"""Tests for scripts/stacklib/services.py: how services are launched, found and stopped.

Run with `uv run python -m unittest discover -s tests`.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from stacklib import IS_WINDOWS, services  # noqa: E402

NETSTAT = """
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1200
  TCP    127.0.0.1:4000         0.0.0.0:0              LISTENING       3808
  TCP    127.0.0.1:4000         127.0.0.1:51000        ESTABLISHED     3808
  TCP    127.0.0.1:51000        127.0.0.1:4000         ESTABLISHED     999
  TCP    127.0.0.1:40000        0.0.0.0:0              LISTENING       77
  TCP    [::1]:4000             [::]:0                 LISTENING       3810
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ParseListeners(unittest.TestCase):
    def test_only_listening_sockets_on_the_exact_port(self):
        self.assertEqual(services.parse_listeners(NETSTAT, 4000), [3808, 3810])

    def test_no_listener(self):
        self.assertEqual(services.parse_listeners(NETSTAT, 6006), [])


class LaunchFlags(unittest.TestCase):
    @unittest.skipUnless(IS_WINDOWS, "Windows creation flags")
    def test_hidden_console_not_detached(self):
        # DETACHED_PROCESS gives each console grandchild (the real interpreter behind a venv launcher or uv.exe) a
        # new visible console window, and closing it kills the service. CREATE_NO_WINDOW keeps the tree windowless.
        self.assertTrue(services.WINDOWS_FLAGS & subprocess.CREATE_NO_WINDOW)
        self.assertTrue(services.WINDOWS_FLAGS & subprocess.CREATE_NEW_PROCESS_GROUP)
        self.assertFalse(services.WINDOWS_FLAGS & subprocess.DETACHED_PROCESS)


class Lifecycle(unittest.TestCase):
    """Start a real HTTP server as a service through start(), find it through status(), stop its tree."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.port = _free_port()
        self.profile = {"data_dir": self.tmp.name, "ports": {"orchestrator": self.port}}
        # Started the way the real services are: a launcher (this venv's python) whose child serves the port.
        child = f"import subprocess, sys; sys.exit(subprocess.call([sys.executable, '-m', 'http.server', '{self.port}', '--bind', '127.0.0.1']))"
        cmds = {"orchestrator": {"cmd": [sys.executable, "-c", child], "cwd": self.tmp.name, "env": None}}
        patches = [
            mock.patch.object(services, "commands", return_value=cmds),
            mock.patch.object(services, "health_url", side_effect=lambda p, s: f"http://127.0.0.1:{self.port}/"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(lambda: services.stop(self.profile, ["orchestrator"]))
        self.addCleanup(self.tmp.cleanup)

    def _state(self) -> str:
        return next(r for r in services.status(self.profile) if r["service"] == "orchestrator")["state"]

    def test_start_status_stop(self):
        self.assertEqual(self._state(), "stopped")
        services.start(self.profile, ["orchestrator"])
        self.assertTrue(services.wait_healthy(self.profile, ["orchestrator"], timeout=30)["orchestrator"])
        self.assertEqual(self._state(), "running")
        listeners = services.port_pids(self.port)
        self.assertTrue(listeners)

        services.stop(self.profile, ["orchestrator"])
        time.sleep(1)
        self.assertEqual(self._state(), "stopped")
        self.assertEqual(services.port_pids(self.port), [])  # the child that served the port is gone too

    def test_status_and_stop_without_a_pid_file(self):
        # A copy started outside the app (or before it restarted) still shows as running and can be stopped.
        proc = subprocess.Popen([sys.executable, "-m", "http.server", str(self.port), "--bind", "127.0.0.1"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proc.kill)
        self.assertTrue(services.wait_healthy(self.profile, ["orchestrator"], timeout=30)["orchestrator"])
        self.assertEqual(self._state(), "running")
        services.stop(self.profile, ["orchestrator"])
        proc.wait(timeout=10)
        self.assertEqual(self._state(), "stopped")


if __name__ == "__main__":
    unittest.main()
