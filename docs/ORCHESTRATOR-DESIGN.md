# Orchestrator design (implemented 2026-10-24)

> Status 2026-10-26: direction changed to private first (`docs/plans/`). Automatic cloud tiers, the orchestrator MCP
> server and Phoenix are slated for removal (`docs/plans/SHARED-COMPONENTS.md` section 5). This document still
> describes what is deployed today.

This document records the architecture that replaced the Deep-Architect plan (`docs/archive/DESIGN-2025.md`)
and the hand-rolled router. It was written on the target machine after the empirical checks in
`docs/HANDOFF-2026-10-24.md` section 6 step 0, so every environment claim below was observed, not assumed.
Measurements live in `memory/state.md`; lessons in `memory/lessons.md`.

## 1. Goals (unchanged from the handoff)

1. Right tool per bandwidth tier: tiny local for autocomplete, local MoE for cheap/simple work, cloud for heavy.
2. Self-developing: prompts, routing and lessons improve from traces, always human-approved.
3. Minimal cost: the Claude Max subscription covers interactive heavy work; API dollars only where a tier needs them.
4. Intuitive: one name per department on every surface; composed from open-source tools, no custom harness.

## 2. Environment found on SEKAIHOME (differs from the handoff's assumptions)

| Assumed | Found | Consequence |
|---|---|---|
| Ollama installed natively | not installed | installed 0.40.11 via winget; models relocated to `D:\ollama\models` (C: had 52 GB free) |
| Docker Desktop + WSL2 present | neither installed | all services run natively; WSL2 would reserve RAM the MoE experts need. Compose kept as an optional, untested path |
| Open WebUI running | not running | installed as a `uv tool`; port 3000 |
| RAM unknown | 32 GB DDR4-2133 (2x16) | MoE tier viable; CPU-side expert bandwidth (~34 GB/s theoretical) caps decode speed |
| Billing unknown (owner said: assume Pro) | account is Max 5x (`claude_max`, `default_claude_max_5x`) | same topology as Pro: subscription for Claude Code, no API key yet; Max includes API credits (confirm in Console) |
| Ollama cannot offload MoE experts (needs llama-server) | refuted: Ollama >= 0.30 runs GGUF through upstream llama-server with `LLAMA_ARG_FIT=on`, which is MoE-aware; `LLAMA_ARG_N_CPU_MOE` passes through | no separate llama-server; one inference engine |
| LiteLLM "verified at 1.108.0" | latest release is 1.106.3 (2026-10-24); it contains `complexity_router`, `adaptive_router`, `/v1/messages` bridge | pinned 1.106.3 |
| Claude Code CLI version unknown | desktop/VS Code extension 2.1.296, CLI 2.1.302 installed | AGENTS.md native (>=2.1.277) and `haiku` -> `claude-haiku-5-5` (>=2.1.293) both hold |

## 3. Decision table (handoff section 2, with outcomes)

| Path | Decision | Outcome |
|---|---|---|
| `docs/DESIGN.md` | superseded | moved to `docs/archive/DESIGN-2025.md`; pre-mortem, circuit breaker, spend cap, VRAM-aware context, architect/critic debate, lessons write-back were ported (section 10) |
| `router/` | retire | deleted; prompts salvaged into `agents/*.yaml` with the complexity keyword lists dropped |
| `config/ollama/Modelfile.*`, `scripts/create-agents.sh` | drop | deleted; prompts are injected at request time (Claude Code agent files, orchestrator, Open WebUI workspace models) so one base model serves all departments |
| `config/vscode/continue.config.json` | delete | deleted; `config/continue/config.yaml` keeps only the autocomplete/embed roles (Continue is read-only upstream) |
| `infrastructure/docker-compose.yml` | rewrite | rewritten without an Ollama container; optional and untested here |
| `scripts/*.sh`, `README.md` | rewrite cross-platform | `scripts/stack.py` (Python via uv) with `setup.ps1`/`setup.sh` wrappers; README rewritten |
| `AGENTS.md` | repurpose as short stable instructions | done; mutable state moved to `memory/state.md`, lessons to `memory/lessons.md`; `CLAUDE.md` imports all three |

## 4. Architecture (as deployed)

```
surfaces     Claude Code (profile A: Anthropic direct on the subscription | profile B: ANTHROPIC_BASE_URL -> gateway)
             OpenCode (provider litellm) · Open WebUI (OpenAI connection -> gateway) · promptfoo (evals) · Continue (FIM only)
                 │ Anthropic /v1/messages            │ OpenAI /v1/chat/completions, /v1/embeddings
                 ▼                                    ▼
gateway      LiteLLM proxy 1.106.3  127.0.0.1:4000  (native uv tool; config generated per machine)
               model_list: local-fim, local-embed, local-small, local-primary, local-reviewer, [cloud-cheap/default/heavy]
                           <dept> = auto_router/complexity_router (SIMPLE/MEDIUM/COMPLEX/REASONING -> aliases above)
                           <dept>-local, <dept>-cloud (explicit tier)
               router_settings: context_window_fallbacks, cooldown, [default_fallbacks -> cloud-default]
               callbacks: custom_callbacks (JSONL traces) + otel (-> Phoenix)
                 │                                                    │
engines      Ollama 0.40.11 native, 127.0.0.1:11434                   Anthropic API (only when ANTHROPIC_API_KEY is set)
             qwen2.5-coder:1.5b-base · nomic-embed-text · qwen3.5:9b · qwen3.6:35b-a3b-coding · flint:40b-a2b
orchestration  FastMCP 4.1.3 server 127.0.0.1:8765/mcp: list_departments, delegate(dept, task, tier, wait) -> job,
               get_job, cancel_job, record_lesson; SQLite job store; bearer auth; calls the gateway
observability  traces/litellm/*.jsonl (per request: alias, served model, routing decision, tokens, cost, latency,
               Claude Code request class, Ollama load/prompt/generation durations) · traces/claude/*.jsonl
               (Stop/SubagentStop/PostToolUse hooks) · Phoenix :6006 (operation spans by process/model; tray aggregates
               token totals, average durations and cloud cost over selectable periods)
self-dev     scripts/retro.py -> retro/reports/<date>.md (+ proposals) -> /retro skill applies approved deltas ->
             build -> promptfoo gate (evals/<dept>) -> commit/PR. Never auto-merge.
state        machines/<HOST>.yaml (hardware class, models, Ollama env) · agents/<id>.yaml (single source of truth)
             memory/state.md · memory/lessons.md · memory/claude/ (Claude Code auto memory via autoMemoryDirectory)
```

Everything that depends on hardware is derived from `machines/_defaults.yaml` (hardware classes) and
`machines/<HOST>.yaml` (detected facts + overrides). `uv run scripts/stack.py doctor --write-profile` on a new
machine creates its profile; `build` regenerates every derived file. This is the "configurable when I upgrade
or add machines" requirement.

## 5. Bandwidth tiers

| Tier | Serves | Used for | Moves up when |
|---|---|---|---|
| T0 autocomplete | `local-fim` = qwen2.5-coder:1.5b-base, pinned (`keep_alive -1`) | editor FIM, embeddings (`local-embed`) | never |
| T1 local small | `local-small` = qwen3.5:9b @16k | gateway housekeeping (titles), `haiku` alias in profile B, retro triage | n/a |
| T2 local primary | `local-primary` = qwen3.6:35b-a3b-coding @32k, pinned | SIMPLE/MEDIUM tiers of every department, `sonnet`/`opus` aliases in profile B | context > 90% of 32k, stall (same tool call repeated twice in six), plan mode on security/app-dev/devops, keyword rules, user types `ESCALATE` |
| T3 cloud default | `cloud-default` = claude-sonnet-5-5 | COMPLEX tiers, default fallback | security/code-review REASONING |
| T4 cloud heavy | `cloud-heavy` = claude-opus-5-5 | security + code-review REASONING tier | - |
| cheap cloud | `cloud-cheap` = claude-haiku-5-5 | docs COMPLEX tier, retro reflection when chosen | - |

With no API key every cloud target is rewritten to `local-primary` at build time, so the stack is fully
local by default. `claude-fable-5-1` is never auto-routed.

## 6. Model lineup and memory budget (12 GB VRAM, 32 GB RAM, ~1.1 GB WDDM idle)

| Model | Download | Where it sits | Notes |
|---|---|---|---|
| qwen2.5-coder:1.5b-base | 986 MB | VRAM, pinned (~1.3 GB) | Apache-2.0 FIM |
| nomic-embed-text | 274 MB | VRAM on demand (<1 GB) | embeddings |
| qwen3.5:9b | 6.6 GB | VRAM (~7.5 GB @16k with q8_0 KV) | swaps against the primary; `OLLAMA_MAX_LOADED_MODELS=2` keeps FIM + one large model |
| qwen3.6:35b-a3b-coding | 23 GB | attention + shared weights in VRAM (~9-10 GB), experts in RAM (~14 GB) | llama.cpp fit places experts automatically; `LLAMA_ARG_N_CPU_MOE` is the manual knob |
| flint:40b-a2b | 23 GB | same shape, 2.5B active | candidate second reviewer / alternative primary; A/B via `bench` and evals |

Ollama environment (user variables, set by `setup`): `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`,
`OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_MAX_QUEUE=32`, `OLLAMA_CONTEXT_LENGTH=32768`,
`OLLAMA_KEEP_ALIVE=30m`, `OLLAMA_GPU_OVERHEAD=536870912`, `OLLAMA_LOAD_TIMEOUT=15m`, `OLLAMA_MODELS=D:\ollama\models`.
The MoE class also sends `use_mmap: true` for the primary and reviewer (`primary_options` / `reviewer_options`):
Ollama disables mmap by default on Windows+CUDA, which turns the CPU-side experts into anonymous memory and made
the first load time out under normal desktop memory pressure.
Measured throughput (2026-10-25): MoE primary ~25 tok/s decode with ~1 GB RAM left available; dense 9B ~52 tok/s
with ~18 GB available. Details in `memory/state.md` (section Benchmarks); re-run with `uv run scripts/stack.py bench`.
On that evidence SEKAIHOME overrides the class default: `local-primary` is qwen3.5:9b at 32k, sharing one Ollama
runner with `local-small` (same num_ctx, no use_mmap). The 35B remains the class default for 32 GB machines with less
desktop memory pressure, and returns here by deleting the override in `machines/SEKAIHOME.yaml`.

## 7. Routing (LiteLLM complexity router, per department)

Each department alias is an `auto_router/complexity_router` deployment generated from `routing:` in its YAML:
tiers mapped to the aliases above, `classifier_type: heuristic` (local, <1 ms, no model call),
`stall_escalation_enabled` (window 6, repeat threshold 2), `enable_context_window_escalation` (buffer 0.9),
`route_housekeeping_to_cheapest_tier`, `escalation_keywords: [ESCALATE, "use claude"]`, optional
`plan_mode_min_tier` and `keyword_tier_rules`. Decisions are logged per request (`routing_decision` in the
JSONL trace), shown by `why-routed`, and appended to routed chat responses in Open WebUI with the concrete
deployment model and its Local/Cloud location.
The heuristic classifier is deliberately the starting point; the
retro proposes tier-boundary or keyword changes from evidence, and `adaptive_router` (Thompson sampling,
needs Postgres) is the upgrade path once there is enough traffic.

System prompts are not injected by the gateway. Claude Code carries them in `.claude/agents/*.md`, the
orchestrator and Open WebUI workspace models carry them per request, promptfoo carries them in `prompt.json`.

## 8. Claude Code integration

- **Profile A (default)**: Claude Code talks to Anthropic on the Max subscription. Departments are subagents
  with `model: haiku|sonnet|opus` aliases, `memory: project`, `maxTurns`, `effort`; skills `/retro`,
  `/harden`, `/brainstorm`, `/why-routed`; hooks `Stop`, `SubagentStop`, `PostToolUse(Bash)` -> `traces/claude/`;
  the orchestrator via `.mcp.json` (`${ORCHESTRATOR_BEARER}`; credential-looking names read as empty).
  `CLAUDE_CODE_GATEWAY_HINT_HEADERS=1` so the gateway sees request classes when profile B is used.
- **Profile B** (`scripts/claude-local.ps1|sh`): `CLAUDE_CONFIG_DIR=~/.claude-local`, `ANTHROPIC_BASE_URL` ->
  gateway, `ANTHROPIC_AUTH_TOKEN` = LiteLLM master key (this replaces subscription billing for that process by
  design), `ANTHROPIC_MODEL=local-primary`, `ANTHROPIC_DEFAULT_{HAIKU,SONNET,OPUS}_MODEL` -> local aliases,
  `CLAUDE_CODE_MAX_CONTEXT_TOKENS`/`MAX_OUTPUT_TOKENS`/`AUTO_COMPACT_WINDOW` sized to the local `num_ctx`,
  `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`. Mixed local/cloud in one process = set
  `claude_code.local_profile.opus_model: cloud-default` in the machine profile once an API key exists.
- Auto memory is redirected into the repo (`autoMemoryDirectory` -> `memory/claude/`, absolute path written to
  `.claude/settings.local.json` by `setup`), so Claude's own notes are versioned next to `lessons.md`.

## 9. Self-development loop (human-gated)

1. Capture: gateway JSONL traces (routing decision, cost, latency, request class), Claude Code hook traces
   (tool use, test pass/fail regexes, ESCALATE sentinel), Phoenix traces for inspection, Open WebUI thumbs
   (export endpoint; not yet wired).
2. `scripts/retro.py --days 7`: per-department stats -> reflection model (`local-small` by default,
   `cloud-cheap` when chosen) proposes at most 3 deltas restricted to `agents/<id>.yaml`, `memory/lessons.md`,
   `machines/<host>.yaml` -> `retro/reports/<date>.md` + `.proposals.json`; `--pr` pushes a `retro/<date>` branch.
3. `/retro` in Claude Code shows the deltas as diffs; approved ones are applied, `build` regenerates, and the
   department's promptfoo gate (`evals/<id>/promptfooconfig.yaml`, run 3x) must not regress.
4. The owner commits/merges. Nothing is applied or merged automatically.
Promotion/demotion of local models is a `machines/<host>.yaml` change proposed the same way.

## 10. Ported from the old design

| Old mechanism | Where it lives now |
|---|---|
| Pre-mortem register | this table + `memory/lessons.md`; thermal/VRAM telemetry replaced by `bench` and `ollama ps` |
| Circuit breaker on repeated tool calls | LiteLLM `stall_escalation` (tier bump) + bounded `maxTurns` on subagents |
| Cloud spend cap | cloud tiers off without a key; LiteLLM virtual-key budgets when Postgres is added; `retro` reports cost |
| VRAM-aware `num_ctx` | hardware class -> `primary_num_ctx`/`small_num_ctx`; `context_window_fallbacks` |
| Architect/critic brainstorm | `/brainstorm` skill (app-dev vs code-review subagents -> ADR in `docs/decisions/`) |
| Lessons write-back | `record_lesson` MCP tool, `/harden` step 5, `memory/lessons.md` |
| 9-hour autonomous session | removed; bounded 15-60 minute tasks with human checkpoints (`agents/_common.md`) |

## 11. Security posture

Gateway and MCP bind to 127.0.0.1 and require bearer tokens generated into `.env`. Department tool
allowlists are least-privilege in Claude Code (`security` and `code-review` cannot edit). Tool output,
file contents and web pages are treated as data (`agents/_common.md`). The orchestrator marks every tool with
MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`). Traces store no prompt or file text.

## 12. Not done / open

- Open WebUI first-run (admin user, import `config/openwebui/*.json`, add the MCP server) is a manual step.
- Services started from a Claude Code tool shell may stop when that session ends; persistence is open
  (`memory/state.md`, open item 2). Smart App Control blocked the unsigned `~/.local/bin` uv launchers on SEKAIHOME, so
  `stack.py up` starts uv tools through their environment's python.exe and identifies them by pid plus start time.
- Open WebUI thumbs export -> traces, and Prometheus/Grafana + `nvidia_gpu_exporter`, are documented but not wired.
- `adaptive_router`, virtual-key budgets and Langfuse need Postgres; deferred until traffic justifies them.
- Cloud tiers are untested on this machine (no API key). `drop_params` is relied on to strip sampling params for Anthropic 5.5.
- Docker compose file is untested here.
- Claude Code profile B was configured but only the gateway's `/v1/messages` path was smoke-tested; run
  `scripts/claude-local.ps1` for a live session test.
