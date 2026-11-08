"""pytest setup shared by every test module.

Code under test records model calls for the tray's Usage tab (scripts/stacklib/usage_log.py); without this, a test that
runs a warm-up or a transcription against a test double would append records to the checkout's real traces/usage.
Tests that check what is written pass their own temporary folder.
"""
import os

os.environ["AGENT_STACK_USAGE_DIR"] = "off"


import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


@pytest.fixture(autouse=True)
def _no_live_ollama(monkeypatch):
    """Feature status and the installer ask the running Ollama (/api/tags) and read the Ollama app's settings database.
    Keep tests off this machine's real ones: Ollama "not running" and no Model location, unless a test patches them."""
    from stacklib import features

    monkeypatch.setattr(features, "ollama_models", lambda profile: None)
    monkeypatch.setattr(features, "app_model_store", lambda: "")


@pytest.fixture(autouse=True)
def _no_live_web_filter(monkeypatch, tmp_path):
    """The web filter downloads lists, reads this PC's DNS servers and writes the Claude security audit's list under
    %LOCALAPPDATA%. Keep tests off all three: no network, no DNS servers, and the audit's folder in a temp dir."""
    from stacklib import webfilter

    def no_download(url, timeout=60):
        raise OSError(f"tests do not download ({url})")

    monkeypatch.setattr(webfilter, "download", no_download)
    monkeypatch.setattr(webfilter, "dns_servers", lambda: [])
    monkeypatch.setattr(webfilter, "audit_dir", lambda: tmp_path / "claude-security-audit")
