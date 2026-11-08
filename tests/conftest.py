"""pytest setup shared by every test module.

Code under test records model calls for the tray's Usage tab (scripts/stacklib/usage_log.py); without this, a test that
runs a warm-up or a transcription against a test double would append records to the checkout's real traces/usage.
Tests that check what is written pass their own temporary folder.
"""
import os

os.environ["AGENT_STACK_USAGE_DIR"] = "off"
