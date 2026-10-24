# AGENTS.md — Deep-Architect Session State
## [Meta]
session_id: handoff-20261024
phase: redesign-research-complete
model_local: (not configured — see docs/HANDOFF-2026-10-24.md §4.3)
model_cloud: claude-sonnet-5-5 (default) / claude-opus-5-5 (heavy) / claude-haiku-5-5 (cheap, confirm ID)
circuit_breaker_trips: 0
auto_escalate: false
require_phase_approval: true

## [Current State]
- The Deep-Architect plan in docs/DESIGN.md is SUPERSEDED. Read docs/HANDOFF-2026-10-24.md before doing anything.
- Research + critique phase is complete; outputs live in docs/research/ (index: docs/research/README.md).
- Adversarial verification of load-bearing claims was stopped early (3/24 checked). Treat unchecked claims as unverified.
- Nothing from the new architecture is implemented yet. router/, config/ollama/, config/vscode/ are slated for removal.
- Branch: claude/local-coding-agents-setup-U45yO, PR #1 open.

## [Lessons Learned]
- [2026-10-24] Do not rebuild the agent harness: Claude Code / OpenCode / Cline already ship loops, tools, subagents, hooks, MCP, AGENTS.md.
- [2026-10-24] A hand-rolled OpenAI-compatible proxy breaks tool-using clients; use LiteLLM (ollama_chat/ for tools, /v1/messages for Claude Code).
- [2026-10-24] Run Ollama natively on Windows, not in Docker; reach it at host.docker.internal:11434. One large local model resident at a time on 12 GB.
- [2026-10-24] Haiku 5.5 at $0.10/$0.50 per MTok changes the local-vs-cloud break-even; local pays off for privacy, autocomplete, and the big MoE tier.
- [2026-10-24] Since 2026-10-21 temperature/top_p/top_k return HTTP 400 on every Claude model; cost lever is output_config.effort.
- [2026-10-24] Keep one source of truth for department prompts and generate per-tool files; duplicated prompts drifted within one session.
- [2026-10-24] Self-development = human-gated nightly PR loop with an eval gate, never auto-merge.

## [Next Steps]
1. Step 0 of the handoff: 30-minute empirical verification on the owner's Windows machine (RAM, Ollama version/tags, Claude Code version, /v1/models, LiteLLM tag).
2. Ask the owner the 6 open questions in docs/HANDOFF-2026-10-24.md §5 (RAM, billing mode, privacy, editor, primary surface, licences).
3. Write docs/ORCHESTRATOR-DESIGN.md (judge panel or direct from HANDOFF §4).
4. Implement per HANDOFF §6 Step 2; delete superseded files; rewrite README; restructure this file into short stable instructions and move state to memory/state.md.
5. Verify, review, commit, push to the branch.

## [Counterpoints Log]
- Approach A: bespoke VS Code extension with 4-phase FSM (docs/DESIGN.md)
  - Counterpoint: reinvents ~80% of Claude Code/OpenCode; 9-hour autonomous local sessions unrealistic on a 14B Q4 model.
  - Resolution: thin orchestration over existing harnesses; bounded 15-60 min tasks with checkpoints.
- Approach B: custom FastAPI router with keyword+length routing (router/main.py)
  - Counterpoint: no tools passthrough, no fallback, no usage log; routing signals are guesses.
  - Resolution: LiteLLM proxy with per-department complexity_router; decisions logged for the retro loop.
- Approach C: Langfuse for observability
  - Counterpoint: 6 containers / ~16 GiB next to Ollama on a 32 GB box.
  - Resolution: LiteLLM spend logs + Phoenix (1 container) + Prometheus/Grafana; Langfuse is the upgrade path.

## [Escalation Log]
- [2026-10-24] Reason: cloud sandbox could not reach ollama.com / huggingface.co / docs.litellm.ai; many model/tag/size claims are medium confidence.
  Resolution: handed to on-prem agent for empirical verification (HANDOFF §6 Step 0).
