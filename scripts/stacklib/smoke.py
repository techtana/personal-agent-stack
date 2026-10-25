"""Smoke tests: gateway, tool round trips (OpenAI and Anthropic formats), embeddings, orchestrator MCP."""
from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request

from . import env_value, info, load_dotenv

TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather for a city",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
    },
}
ANTHROPIC_TOOL = {
    "name": "get_weather",
    "description": "Get weather for a city",
    "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
}
Q = "What is the weather in Paris? Use the tool."


def _post(url: str, payload: dict, headers: dict, timeout: int = 600) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return e.code, {"error": str(e)}
    except (urllib.error.URLError, OSError) as e:
        return 0, {"error": str(e)}


def _get(url: str, headers: dict, timeout: int = 30) -> tuple[int, dict]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:300]}
    except (urllib.error.URLError, OSError) as e:
        return 0, {"error": str(e)}


def _text(j: dict) -> str:
    return ((j.get("choices") or [{}])[0].get("message", {}) or {}).get("content") or ""


def run(profile: dict, dept: str = "docs", skip_mcp: bool = False) -> list[dict]:
    dotenv = load_dotenv()
    master = env_value("LITELLM_MASTER_KEY", dotenv)
    base = f"http://127.0.0.1:{profile['ports']['litellm']}"
    h = {"Authorization": f"Bearer {master}"}
    results: list[dict] = []

    def rec(name: str, ok: bool, detail: str = "") -> None:
        results.append({"test": name, "ok": ok, "detail": detail})
        info(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")

    code, j = _get(f"{base}/v1/models", h)
    ids = [m.get("id") for m in j.get("data", [])] if code == 200 else []
    rec("litellm /v1/models", code == 200 and dept in ids, f"{len(ids)} models; has {dept}={dept in ids}" if code == 200 else json.dumps(j)[:160])

    t0 = time.time()
    # Thinking models spend tokens before answering; give them room or the content comes back empty.
    code, j = _post(f"{base}/v1/chat/completions", {"model": f"{dept}-local", "messages": [{"role": "user", "content": "Reply with exactly the single word OK."}], "max_tokens": 400}, h)
    txt = _text(j) if code == 200 else json.dumps(j)[:200]
    rec("chat completion (dept-local)", code == 200 and "OK" in txt.upper(), f"{time.time() - t0:.1f}s model={j.get('model')} text={txt.strip()[:40]!r} usage={j.get('usage')}")

    code, j = _post(f"{base}/v1/chat/completions", {"model": f"{dept}-local", "messages": [{"role": "user", "content": Q}], "tools": [TOOL], "max_tokens": 200}, h)
    msg = (j.get("choices") or [{}])[0].get("message", {}) if code == 200 else {}
    calls = msg.get("tool_calls") or []
    rec("tool call (OpenAI format)", bool(calls) and calls[0]["function"]["name"] == "get_weather", f"tool_calls={len(calls)} args={calls[0]['function'].get('arguments') if calls else json.dumps(j)[:160]}")
    if calls:
        follow = {
            "model": f"{dept}-local",
            "max_tokens": 100,
            "tools": [TOOL],
            "messages": [{"role": "user", "content": Q}, msg, {"role": "tool", "tool_call_id": calls[0]["id"], "content": json.dumps({"city": "Paris", "temp_c": 18, "sky": "clear"})}],
        }
        code, j = _post(f"{base}/v1/chat/completions", follow, h)
        txt = _text(j) if code == 200 else json.dumps(j)[:200]
        rec("tool result round trip", code == 200 and "18" in txt, f"text={txt.strip()[:60]!r}")

    code, j = _post(f"{base}/v1/messages", {"model": f"{dept}-local", "max_tokens": 200, "tools": [ANTHROPIC_TOOL], "messages": [{"role": "user", "content": Q}]}, {"x-api-key": master, "anthropic-version": "2023-06-01"})
    blocks = j.get("content", []) if code == 200 else []
    tu = [b for b in blocks if b.get("type") == "tool_use"]
    rec("/v1/messages tool_use (Claude Code path)", code == 200 and bool(tu), f"stop={j.get('stop_reason')} blocks={[b.get('type') for b in blocks] or json.dumps(j)[:160]}")

    code, j = _post(f"{base}/v1/chat/completions", {"model": dept, "messages": [{"role": "user", "content": "Say hi in three words."}], "max_tokens": 20}, h)
    rec("department router alias", code == 200, f"served={j.get('model')} text={(_text(j) or json.dumps(j)[:120]).strip()[:40]!r}")

    code, j = _post(f"{base}/v1/embeddings", {"model": "local-embed", "input": "hello world"}, h)
    dims = len(((j.get("data") or [{}])[0]).get("embedding", [])) if code == 200 else 0
    rec("embeddings (local-embed)", dims > 0, f"dims={dims}" if dims else json.dumps(j)[:160])

    if not skip_mcp:
        rec("orchestrator MCP tools/list", *asyncio.run(_mcp_check(profile)))
    return results


async def _mcp_check(profile: dict) -> tuple[bool, str]:
    try:
        from fastmcp import Client
        from fastmcp.client.auth import BearerAuth
    except ImportError as e:
        return False, f"fastmcp client unavailable: {e}"
    url = f"http://127.0.0.1:{profile['ports']['orchestrator']}/mcp"
    token = env_value("ORCHESTRATOR_BEARER", load_dotenv())
    try:
        async with Client(url, auth=BearerAuth(token)) as c:
            tools = await c.list_tools()
            names = sorted(t.name for t in tools)
            res = await c.call_tool("list_departments", {})
            data = getattr(res, "data", None)
            return "delegate" in names, f"tools={names} departments={len(data) if isinstance(data, list) else '?'}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:200]}"
