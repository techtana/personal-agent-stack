"""Read LiteLLM / Claude Code JSONL traces for `why-routed` and the retrospective."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from . import TRACES_DIR


def read_jsonl(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for p in paths:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def recent_files(sub: str, days: int) -> list[Path]:
    d = TRACES_DIR / sub
    today = date.today()
    return [d / f"{(today - timedelta(days=i)).isoformat()}.jsonl" for i in reversed(range(days))]


def litellm_rows(days: int = 7) -> list[dict]:
    return read_jsonl(recent_files("litellm", days))


def claude_rows(days: int = 7) -> list[dict]:
    return read_jsonl(recent_files("claude", days))


def format_routed(rows: list[dict]) -> str:
    lines = []
    for r in rows:
        rd = r.get("routing_decision") or {}
        signals = rd.get("signals") or []
        lines.append(
            f"{(r.get('ts') or '')[:19]}  req={str(r.get('requested_model') or '?'):<16} served={str(r.get('model') or '?'):<30} "
            f"tier={str(rd.get('tier') or '-'):<9} cause={str(rd.get('cause') or '-'):<26} signals={','.join(map(str, signals)) or '-'}  "
            f"tok={r.get('prompt_tokens', 0)}/{r.get('completion_tokens', 0)} cost=${float(r.get('cost') or 0):.4f} "
            f"{r.get('latency_ms') or 0}ms class={r.get('request_class') or '-'} {'ERR' if r.get('status') == 'failure' else ''}"
        )
    return "\n".join(lines) if lines else "(no LiteLLM traces yet; traces/litellm/*.jsonl is written by the gateway callback)"
