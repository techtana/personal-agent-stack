#!/usr/bin/env python3
"""Record on-prem verification results in docs/research/verification-status.json.

Usage: uv run scripts/update_verification.py            (idempotent; edits claims by index)
Each entry below adds an `onprem` vote with what was observed on SEKAIHOME on 2026-10-24 and sets the
claim's status/verdict. Extend the RESULTS list when new measurements land (e.g. after `stack.py bench`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "docs" / "research" / "verification-status.json"

RESULTS: list[dict] = [
    {"index": 2, "verdict": "contested", "status": "complete", "refuted": False,
     "note": "Measured on SEKAIHOME (RTX 3060 12GB, 32GB DDR4-2133, Ryzen 5 5500) with Ollama 0.40.11 llama-server fit, not bare llama.cpp: see memory/state.md Benchmarks. The 39-47 tok/s figures assume faster RAM/CPU."},
    {"index": 3, "verdict": "REFUTED", "status": "complete", "refuted": True,
     "note": "Ollama 0.40.11 runs GGUF via upstream llama-server with LLAMA_ARG_FIT=on (MoE-aware placement); LLAMA_ARG_N_CPU_MOE passes through. No separate llama-server needed; adopted the recency lens' corrected claim."},
    {"index": 4, "verdict": "holding", "status": "complete", "refuted": False,
     "note": "ollama.com/library/qwen3.6 lists qwen3.6:35b-a3b (22-24 GB), qwen3.6:35b-a3b-coding, qwen3.6:27b and variants; pulled qwen3.6:35b-a3b-coding on 2026-10-24."},
    {"index": 6, "verdict": "holding", "status": "complete", "refuted": False,
     "note": "qwen3.5:9b exists (6.6 GB download); loaded and served tool calls through LiteLLM ollama_chat on 2026-10-24."},
    {"index": 8, "verdict": "holding", "status": "complete", "refuted": False,
     "note": "qwen2.5-coder:1.5b-base exists (986 MB) and was pulled; Continue is read-only upstream so only its autocomplete role is kept."},
    {"index": 13, "verdict": "holding", "status": "complete", "refuted": False,
     "note": "GitHub API: anomalyco/opencode and sst/opencode both report v1.19.4 released 2026-10-22; npm opencode-ai 1.19.4."},
    {"index": 17, "verdict": "holding", "status": "complete", "refuted": False,
     "note": "code.claude.com/docs/en/llm-gateway-protocol (read 2026-10-24): ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN/ANTHROPIC_API_KEY; credential variables replace subscription billing; CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS and gateway hint headers documented."},
    {"index": 18, "verdict": "holding", "status": "complete", "refuted": False,
     "note": "code.claude.com/docs/en/sub-agents (read 2026-10-24) confirms name/description/tools/disallowedTools/model/permissionMode/skills/memory/maxTurns/background/isolation/effort/mcpServers/hooks/color/autoCompactWindow. Non-Claude model strings are not documented."},
    {"index": 19, "verdict": "holding", "status": "complete", "refuted": False,
     "note": "code.claude.com/docs/en/memory (read 2026-10-24): AGENTS.md read when no CLAUDE.md exists (v2.1.277+); @AGENTS.md import; setting cc-plugin-agents-md@builtin instructionFiles claude-md-and-agents-md; autoMemoryDirectory accepts absolute or ~/ paths."},
    {"index": 22, "verdict": "holding", "status": "complete", "refuted": False,
     "note": "Open WebUI v0.12.3 (GitHub release 2026-10-16) installed via uv tool and running; /api/version reports 0.12.3. Import/export endpoints /api/v1/models/{import,export} exist; ModelForm uses access_grants (not access_control)."},
]


def main() -> int:
    doc = json.loads(PATH.read_text(encoding="utf-8"))
    by_index = {c["index"]: c for c in doc["claims"]}
    changed = 0
    for r in RESULTS:
        c = by_index.get(r["index"])
        if not c:
            print(f"claim {r['index']} not found", file=sys.stderr)
            continue
        c.setdefault("votes", {})["onprem"] = {"refuted": r["refuted"], "confidence": "high", "checked_on": "2026-10-24", "machine": "SEKAIHOME", "reasoning": r["note"]}
        c["status"] = r["status"]
        c["verdict_so_far"] = r["verdict"]
        changed += 1
    doc["onprem_verification"] = {"date": "2026-10-24", "machine": "SEKAIHOME", "claims_updated": [r["index"] for r in RESULTS], "see": "memory/state.md, docs/ORCHESTRATOR-DESIGN.md section 2"}
    PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"updated {changed} claims in {PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
