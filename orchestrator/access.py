"""Who may call the agent tools: the stack's bearer (Open WebUI, OpenCode), and Claude's own bearer while the tray's
Claude switch is on.

ORCHESTRATOR_BEARER is the stack's; ORCHESTRATOR_CLAUDE_BEARER is Claude Code's (.mcp.json). Claude's is checked
against the switch file on every request (scripts/stacklib/claude_access.py), so turning Claude off in the tray refuses
its next call without a restart. Neither name ends in _TOKEN or _API_KEY, which Claude Code blanks in .mcp.json.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastmcp.server.auth import StaticTokenVerifier

_SCRIPTS = str(Path(__file__).resolve().parents[1] / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from stacklib.claude_access import ALIAS, Switch  # noqa: E402 - standard library only

SCOPE = "orchestrate"


class StackTokenVerifier(StaticTokenVerifier):
    """The two bearers; Claude's counts only while the switch is on."""

    def __init__(self, stack_bearer: str, claude_bearer: str = "", switch: Switch | None = None):
        tokens = {stack_bearer: {"client_id": "local-stack", "scopes": [SCOPE]}}
        if claude_bearer and claude_bearer != stack_bearer:
            tokens[claude_bearer] = {"client_id": ALIAS, "scopes": [SCOPE]}
        super().__init__(tokens=tokens, required_scopes=[SCOPE])
        self.switch = switch or Switch.from_env()

    async def verify_token(self, token: str):
        found = await super().verify_token(token)
        if found is not None and found.client_id == ALIAS and not self.switch.on():
            return None
        return found
