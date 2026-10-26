#!/usr/bin/env python3
"""Claude Code hook (Stop, SubagentStop, PostToolUse:Bash). Stdlib only; never blocks (always exit 0).

Appends one JSON line per event to traces/claude/YYYY-MM-DD.jsonl with what the retrospective needs:
agent type, tool name and duration, test pass/fail detected in Bash output, the ESCALATE sentinel, message size.
No prompt or file contents are stored.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TEST_PATTERNS = [
    (re.compile(r"(\d+) passed"), re.compile(r"(\d+) failed")),  # pytest
    (re.compile(r"Tests:\s+(\d+) passed"), re.compile(r"Tests:.*?(\d+) failed")),  # jest / vitest
    (re.compile(r"^ok\s", re.M), re.compile(r"^FAIL\s", re.M)),  # go test
    (re.compile(r"test result: ok\. (\d+) passed"), re.compile(r"test result: FAILED\. \d+ passed; (\d+) failed")),  # cargo
]
TEST_CMD = re.compile(r"\b(pytest|vitest|jest|npm test|pnpm test|yarn test|go test|cargo test|promptfoo eval)\b")


def project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def _n(m) -> int:
    if not m:
        return 0
    try:
        return int(m.group(1))
    except (IndexError, ValueError):
        return 1


def detect_tests(text: str) -> dict | None:
    for ok_re, fail_re in TEST_PATTERNS:
        ok, fail = ok_re.search(text), fail_re.search(text)
        if ok or fail:
            return {"passed": _n(ok), "failed": _n(fail), "ok": bool(ok) and not fail}
    return None


def count_tool_uses(transcript: str | None) -> int | None:
    if not transcript:
        return None
    p = Path(os.path.expanduser(transcript))
    if not p.exists():
        return None
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return text.count('"type":"tool_use"') + text.count('"type": "tool_use"')


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    ev = payload.get("hook_event_name", "unknown")
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": ev,
        "session_id": payload.get("session_id"),
        "agent_type": payload.get("agent_type"),
        "agent_id": payload.get("agent_id"),
        "permission_mode": payload.get("permission_mode"),
        "cwd": payload.get("cwd"),
    }
    if ev in ("Stop", "SubagentStop"):
        msg = payload.get("last_assistant_message") or ""
        rec.update(
            last_message_chars=len(msg),
            last_message_head=msg[:200],
            escalated="ESCALATE:" in msg,
            tool_uses=count_tool_uses(payload.get("agent_transcript_path") or payload.get("transcript_path")),
        )
    elif ev == "PostToolUse":
        ti = payload.get("tool_input") or {}
        tr = payload.get("tool_response") or {}
        text = tr if isinstance(tr, str) else json.dumps(tr)
        cmd = ti.get("command") if isinstance(ti, dict) else None
        rec.update(
            tool=payload.get("tool_name"),
            duration_ms=payload.get("duration_ms"),
            command=(cmd or "")[:300],
            is_test_command=bool(cmd and TEST_CMD.search(cmd)),
        )
        tests = detect_tests(text)
        if tests:
            rec["tests"] = tests
        if isinstance(tr, dict):
            rec["tool_error"] = bool(tr.get("is_error") or tr.get("interrupted"))
    out = project_dir() / "traces" / "claude"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{datetime.now().date().isoformat()}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 - a logging hook must never block the agent
        sys.exit(0)
