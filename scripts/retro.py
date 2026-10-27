#!/usr/bin/env python3
"""Nightly retrospective: traces -> per-department stats -> <=3 proposed deltas -> report (+ optional PR branch).

Human-gated by design: it never edits prompts, routing or lessons itself. It writes
retro/reports/YYYY-MM-DD.md (committed) and retro/reports/YYYY-MM-DD.proposals.json, and with --pr opens a
branch + PR carrying the report so the owner reviews it in the morning (`/retro` in Claude Code applies approved deltas).

  uv run scripts/stack.py retro --days 7                              # local reflection model (local-small)
  uv run scripts/stack.py retro --days 7 --pr                         # same, and open a PR
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import httpx  # noqa: E402

from stacklib import REPO, env_value, info, load_dotenv, warn  # noqa: E402
from stacklib import profile as prof  # noqa: E402
from stacklib import traces  # noqa: E402

ALLOWLIST = [
    "agents/<id>.yaml (system_prompt bullets, routing tiers, keyword_tier_rules)",
    "memory/lessons.md (append a dated bullet)",
    "machines/<host>.yaml (models.*, primary_num_ctx)",
]
SCHEMA_HINT = (
    '{"deltas": [{"file": "agents/docs.yaml", "change": "one bullet-level change, stated precisely", '
    '"evidence": ["trace ids or counts"], "expected_effect": "one sentence"}], "diagnosis": "<=200 words"}'
)


def _new_dept() -> dict:
    return {"requests": 0, "local": 0, "cloud": 0, "errors": 0, "cost": 0.0, "latency": [], "stall": 0, "kw": 0, "ctx_esc": 0, "plan": 0, "classes": Counter()}


def stats(rows: list[dict], claude: list[dict]) -> dict:
    by: dict[str, dict] = defaultdict(_new_dept)
    for r in rows:
        dept = str(r.get("requested_model") or "?").replace("-local", "").replace("-cloud", "")
        s = by[dept]
        s["requests"] += 1
        s["cost"] += float(r.get("cost") or 0)
        if r.get("latency_ms"):
            s["latency"].append(r["latency_ms"])
        if r.get("status") == "failure":
            s["errors"] += 1
        prov = str(r.get("provider") or "") + str(r.get("model") or "")
        s["cloud" if ("anthropic" in prov or "claude" in prov) else "local"] += 1
        rd = r.get("routing_decision") or {}
        sig = ",".join(map(str, rd.get("signals") or []))
        cause = str(rd.get("cause") or "")
        s["stall"] += "stall" in sig
        s["kw"] += "keyword" in sig or "keyword" in cause
        s["ctx_esc"] += "context_window" in sig or "context_window" in cause
        s["plan"] += "plan_mode" in sig or "plan" in cause
        if r.get("request_class"):
            s["classes"][r["request_class"]] += 1
    tests = [c for c in claude if c.get("tests")]
    stops = [c for c in claude if c.get("event") in ("Stop", "SubagentStop")]
    departments = {}
    for d, s in sorted(by.items()):
        departments[d] = {
            **{k: v for k, v in s.items() if k not in ("latency", "classes")},
            "p50_latency_ms": int(statistics.median(s["latency"])) if s["latency"] else None,
            "request_classes": dict(s["classes"]),
        }
    return {
        "departments": departments,
        "claude_code": {
            "turns": len(stops),
            "escalations": sum(1 for c in stops if c.get("escalated")),
            "test_runs": len(tests),
            "test_runs_green": sum(1 for c in tests if c["tests"].get("ok")),
            "by_agent": dict(Counter(c.get("agent_type") or "main" for c in stops)),
        },
    }


def reflect(summary: dict, model: str, port: int, cap_tokens: int = 1500) -> dict:
    key = env_value("LITELLM_MASTER_KEY", load_dotenv())
    prompt = (
        "You are the retrospective for a local-first coding-agent stack. Below are statistics per department "
        "(requests, local vs cloud share, errors, stall/keyword/context escalations, cost, Claude Code test outcomes).\n"
        f"Propose at most 3 small, evidence-backed deltas restricted to these files: {ALLOWLIST}. "
        "Every tier must stay a private deployment (local-small, local-primary, local-reviewer); prefer moving a "
        "department between them when its errors or escalations justify it; prompt bullet changes only when evidence points at output format or escalation behaviour. "
        "If the data is too thin, return zero deltas and say so.\n"
        f"Respond with JSON only, matching {SCHEMA_HINT}.\n\nSTATS:\n{json.dumps(summary, indent=1)}"
    )
    try:
        r = httpx.post(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "max_tokens": cap_tokens, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}},
            timeout=600,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
        start, end = text.find("{"), text.rfind("}")
        return json.loads(text[start : end + 1])
    except Exception as e:  # noqa: BLE001
        warn(f"reflection failed ({type(e).__name__}: {e}); report will carry stats only")
        return {"deltas": [], "diagnosis": f"reflection unavailable: {e}"}


def render(summary: dict, proposal: dict, days: int, model: str) -> str:
    lines = [
        f"# Retrospective {date.today().isoformat()} (last {days} days)",
        "",
        f"Reflection model: `{model}`. Human-gated: nothing below was applied.",
        "",
        "## Departments",
        "",
        "| dept | req | local | cloud | err | stall | kw | ctx | plan | p50 ms | cost $ |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for d, s in summary["departments"].items():
        lines.append(f"| {d} | {s['requests']} | {s['local']} | {s['cloud']} | {s['errors']} | {s['stall']} | {s['kw']} | {s['ctx_esc']} | {s['plan']} | {s['p50_latency_ms'] or '-'} | {s['cost']:.3f} |")
    cc = summary["claude_code"]
    lines += [
        "",
        "## Claude Code sessions",
        "",
        f"- turns: {cc['turns']} (by agent: {cc['by_agent']})",
        f"- escalations (ESCALATE sentinel): {cc['escalations']}",
        f"- test runs: {cc['test_runs']}, green: {cc['test_runs_green']}",
        "",
        "## Diagnosis",
        "",
        (proposal.get("diagnosis") or "").strip() or "(none)",
        "",
        "## Proposed deltas (max 3)",
        "",
    ]
    for i, d in enumerate(proposal.get("deltas") or [], 1):
        lines += [f"{i}. **{d.get('file')}** - {d.get('change')}", f"   - evidence: {d.get('evidence')}", f"   - expected effect: {d.get('expected_effect')}", ""]
    if not proposal.get("deltas"):
        lines.append("(no deltas proposed)")
    lines += ["", "Apply approved deltas with `/retro` in Claude Code, rebuild (`uv run scripts/stack.py build`) and run the promptfoo gate for touched departments."]
    return "\n".join(lines) + "\n"


def open_pr(report: Path) -> None:
    branch = f"retro/{date.today().isoformat()}"

    def run(*c: str) -> None:
        subprocess.run(c, cwd=REPO, check=True, capture_output=True, text=True)

    run("git", "switch", "-c", branch)
    run("git", "add", str(report), str(report.with_suffix(".proposals.json")))
    run("git", "commit", "-m", f"retro: {date.today().isoformat()} retrospective report")
    run("git", "push", "-u", "origin", branch)
    subprocess.run(["gh", "pr", "create", "--title", f"retro: {date.today().isoformat()}", "--body-file", str(report)], cwd=REPO, check=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--reflect", default="local-small", help="gateway model alias for the reflection step (a private alias such as local-small, or none)")
    ap.add_argument("--pr", action="store_true", help="commit the report on retro/<date> and open a PR with gh")
    a = ap.parse_args()
    p = prof.resolve_profile()
    rows, claude = traces.litellm_rows(a.days), traces.claude_rows(a.days)
    summary = stats(rows, claude)
    info(f"retro: {len(rows)} gateway requests, {len(claude)} Claude Code events over {a.days} days")
    if a.reflect == "none" or not rows:
        proposal = {"deltas": [], "diagnosis": "reflection skipped (no gateway traces yet)" if not rows else "reflection skipped"}
    else:
        proposal = reflect(summary, a.reflect, p["ports"]["litellm"])
    out = REPO / "retro" / "reports" / f"{date.today().isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(summary, proposal, a.days, a.reflect), encoding="utf-8")
    out.with_suffix(".proposals.json").write_text(json.dumps({"summary": summary, "proposal": proposal}, indent=2), encoding="utf-8")
    info(f"retro: wrote {out.relative_to(REPO)}")
    if a.pr:
        open_pr(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
