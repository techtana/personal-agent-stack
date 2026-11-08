"""Read the JSONL traces: the gateway's (traces/litellm), Claude Code's hook (traces/claude) and the usage records
of models run outside the gateway (traces/usage/<source>, written through stacklib/usage_log.py)."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from . import TRACES_DIR

# path -> (mtime_ns, size, rows). The tray summarises up to 31 days of traces every few seconds; only files that
# changed since the last read are parsed again. Callers get copies of the rows, so changing one cannot alter the cache.
_cache: dict[Path, tuple[int, int, list[dict]]] = {}


def _read_one(p: Path) -> list[dict]:
    try:
        st = p.stat()
    except OSError:
        _cache.pop(p, None)
        return []
    hit = _cache.get(p)
    if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
        return hit[2]
    rows: list[dict] = []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    _cache[p] = (st.st_mtime_ns, st.st_size, rows)
    return rows


def read_jsonl(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for p in paths:
        rows.extend(dict(r) for r in _read_one(p))
    return rows


def recent_files(sub: str, days: int) -> list[Path]:
    d = TRACES_DIR / sub
    today = date.today()
    return [d / f"{(today - timedelta(days=i)).isoformat()}.jsonl" for i in reversed(range(days))]


def litellm_rows(days: int = 7) -> list[dict]:
    return read_jsonl(recent_files("litellm", days))


def claude_rows(days: int = 7) -> list[dict]:
    return read_jsonl(recent_files("claude", days))


def usage_rows(days: int = 7) -> list[dict]:
    """Usage records of every source folder under traces/usage for the last `days` local days."""
    root = TRACES_DIR / "usage"
    if not root.is_dir():
        return []
    today = date.today()
    names = [f"{(today - timedelta(days=i)).isoformat()}.jsonl" for i in reversed(range(days))]
    return read_jsonl([src / n for src in sorted(p for p in root.iterdir() if p.is_dir()) for n in names])


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
