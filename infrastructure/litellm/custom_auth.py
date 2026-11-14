"""LiteLLM proxy custom auth: Claude's own gateway key, and the tray's switch for it.

Registered in config.yaml as `general_settings.custom_auth: custom_auth.user_api_key_auth`. LiteLLM calls it for every
request, before its own key check:

- any key but Claude's: it returns None, and LiteLLM's own check decides as before (the master key that Open WebUI,
  OpenClaw, voice typing and the stack's scripts use). litellm-enterprise, which litellm[proxy] installs, passes None
  on to that check; without it LiteLLM would refuse every request, which `stack.py smoke` would show at once;
- Claude's key (LITELLM_CLAUDE_KEY, in Claude Code's profile B): refused while the switch is off (the file in
  AGENT_STACK_CLAUDE_ACCESS_FILE, read again whenever it changes, so the tray's switch needs no restart) and on every
  route but the model calls in CLAUDE_ROUTES (LiteLLM's own "LLM route" test also admits pass-through, trace, RAG and
  file routes); otherwise let through as key alias "claude", which the traces record, so the Usage tab counts Claude
  by its key, not by the name it sends.

config.yaml also sets custom_auth_run_common_checks: LiteLLM skips its common checks (model access, budgets, route
rules) for every key, the master key included, whenever custom_auth is set, unless that flag is on.

What it cannot stop: a program that reads the master key from .env and sends that instead (scripts/stacklib/claude_access.py).
"""
from __future__ import annotations

import hmac
import os
import sys
from pathlib import Path

_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from stacklib.claude_access import ALIAS, GATEWAY_KEY, OFF_MESSAGE, Switch  # noqa: E402 - standard library only

SWITCH = Switch.from_env()
# What Claude Code calls: Anthropic messages (profile B), and the OpenAI-style chat, embeddings and model list.
CLAUDE_ROUTES = frozenset({
    "/v1/messages", "/v1/messages/count_tokens", "/v1/models", "/models", "/v1/chat/completions", "/chat/completions",
    "/v1/embeddings", "/embeddings",
})


def is_claude(api_key) -> bool:
    key = os.environ.get(GATEWAY_KEY, "")
    if not key or key == os.environ.get("LITELLM_MASTER_KEY"):   # the stack's own key is never Claude's
        return False
    return isinstance(api_key, str) and hmac.compare_digest(api_key.encode(), key.encode())


def refusal(route: str, switch_on: bool, model_route: bool) -> str | None:
    """Why a request with Claude's key is refused, or None to let it through."""
    if not switch_on:
        return OFF_MESSAGE
    if not model_route:
        return f"Claude's key works only for model calls on this gateway, not for {route}."
    return None


async def user_api_key_auth(request, api_key: str):
    if not is_claude(api_key):
        return None   # LiteLLM's own check: the master key
    from litellm.proxy._types import LitellmUserRoles, ProxyException, UserAPIKeyAuth
    from litellm.proxy.auth.auth_utils import get_request_route

    route = get_request_route(request=request)
    why = refusal(route, SWITCH.on(), route in CLAUDE_ROUTES)
    if why:
        # 403, not 401: the key is known; a 4xx also keeps the router from retrying it
        raise ProxyException(message=why, type="auth_error", param="api_key", code=403)
    return UserAPIKeyAuth(api_key=api_key, key_alias=ALIAS, user_id=ALIAS, user_role=LitellmUserRoles.INTERNAL_USER)
