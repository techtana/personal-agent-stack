# Deep-Architect: Agentic Orchestrator VS Code Extension
## System Design Document & Implementation Plan

**Session answers:**
- Local model: Model-agnostic (runtime config, designed around 12GB VRAM budget)
- Escalation default: Configurable per-session toggle in UI
- Target stacks: TypeScript/Node.js, Python, multi-language (tree-sitter covers all)
- Phase II gate: Configurable per-session toggle

---

## Context

The project directory `personal-agent-stack/` is currently empty — this is a greenfield build. The goal is a VS Code extension that acts as an **Agentic Orchestrator**: it runs autonomous 9-hour development sessions using a local LLM (via Ollama on RTX 3060 12GB VRAM), manages persistent state through an `AGENTS.md` file, chunks code with AST awareness for RAG, and escalates to Claude API when local reasoning loops. The design must survive thermal events, context bloat, and reasoning loops without losing session state.

**What this is NOT**: a basic Ollama chat wrapper (Continue.dev already does that). The differentiator is orchestration depth — a 4-phase state machine, multi-model brainstorm debate, persistent episodic memory, and hardware-aware pacing.

---

## Pre-Mortem: Why This Fails Without the Right Design

| Failure Mode | Root Cause | Prevention in This Design |
|---|---|---|
| Ollama OOM at hour 3 | VRAM fragmentation + long context | Dynamic `num_ctx` scaling via VRAM telemetry; crash recovery from AGENTS.md checkpoint |
| Model "forgets" the task | Context bloat from 5h of tool call history | ContextPruner at 75% threshold; AGENTS.md re-injected fresh into every prompt |
| Reasoning loop (writes same file 50×) | No feedback mechanism | CircuitBreaker detects repeated 3-call sequence; trips after 2 repetitions |
| Test suite hangs forever | Resource-leaking test spawns | TerminalTool timeout (120s); `taskkill /F /T` on Windows |
| Extension host OOM | Large buffers in Node.js heap | EpisodicLog is append-only to disk; webview tool log capped at 200 entries (circular) |
| Windows GPU driver reset overnight | Power management | Monitor detects pynvml exception; re-initializes Ollama + RAG on resume |
| Cloud API runaway spend | Many circuit breaker trips | CloudBudget cap (20 calls/session); per-call input token cap (8192) |

---

## Three Critical Technical Unknowns (Resolve Before Phase I)

1. **Ollama `context` array stability across restarts** — The NDJSON `context` token array may become invalid after Ollama daemon restart (required by thermal recovery). Must test: restart Ollama mid-conversation and verify continuation coherence. If unstable → always reconstruct from text history, never rely on KV-cache tokens across restarts.

2. **VS Code extension host memory ceiling on Windows 11** — Unknown whether VS Code kills the extension host after sustained memory growth over 9 hours. Must profile: run a memory benchmark session with `--inspect` on extension host, identify GC pressure patterns, set per-component memory budgets before writing any code.

3. **Ollama concurrent request behavior on Windows** — Behavior when a second `/api/generate` arrives while inference is in-flight is undocumented on Windows. Must test: send two simultaneous requests, observe queue vs. reject vs. silent failure. Answer determines whether OllamaAdapter needs a hard serialization mutex (recommended regardless).

---

## Directory Structure

```
personal-agent-stack/
├── package.json                    # VS Code extension manifest
├── tsconfig.json
├── esbuild.config.js
│
├── src/
│   ├── extension.ts                # Activation, command registration
│   │
│   ├── core/
│   │   ├── MessageBus.ts           # Typed EventEmitter3 — all inter-component events
│   │   ├── StateMachine.ts         # 4-phase FSM with guard conditions
│   │   ├── ContextBudget.ts        # Token counting, num_ctx dynamic scaling
│   │   ├── CircuitBreaker.ts       # Loop detection, failure counting, escalation
│   │   └── WorkflowScheduler.ts    # Phase timer, thermal gating, inter-request pacing
│   │
│   ├── adapters/
│   │   ├── OllamaAdapter.ts        # NDJSON stream parser, context token store, model-agnostic
│   │   ├── CloudAdapter.ts         # @anthropic-ai/sdk streaming, cost guard
│   │   └── SidecarAdapter.ts       # JSON-RPC 2.0 over stdio to Python sidecar
│   │
│   ├── agents/
│   │   ├── RepositoryMappingAgent.ts   # Phase I
│   │   ├── BrainstormAgent.ts          # Phase II — adversarial two-thread debate
│   │   ├── ExecutionAgent.ts           # Phase III — TDD loop + tool calling
│   │   └── HardeningAgent.ts           # Phase IV — edge cases, security, docs
│   │
│   ├── tools/
│   │   ├── ToolRegistry.ts         # Maps tool names → handlers; validates Zod schema
│   │   ├── FileSystemTool.ts       # vscode.workspace.fs wrappers
│   │   ├── TerminalTool.ts         # Spawns terminal with timeout + taskkill on Windows
│   │   ├── SearchTool.ts           # Calls sidecar RAG query
│   │   └── TestRunnerTool.ts       # Runs tests, parses output, feeds CircuitBreaker
│   │
│   ├── memory/
│   │   ├── AgentsFile.ts           # Parse/write AGENTS.md sections
│   │   ├── EpisodicLog.ts          # Append-only JSONL to disk — never buffered fully
│   │   └── ContextPruner.ts        # Sliding window + importance scoring; salvages lessons
│   │
│   ├── ui/
│   │   ├── DeepArchitectPanel.ts   # WebviewViewProvider — sidebar panel
│   │   ├── StatusBarManager.ts     # Phase chip, model label, GPU temp item
│   │   └── webview/
│   │       ├── index.html
│   │       ├── main.ts             # Compiled separately with esbuild
│   │       ├── components/
│   │       │   ├── ChainOfThought.tsx   # Streaming token display
│   │       │   ├── AgentsViewer.tsx     # AGENTS.md [Current State] + [Next Steps]
│   │       │   ├── ToolCallLog.tsx      # Circular 200-entry log
│   │       │   ├── PhaseTimeline.tsx    # Progress bar + phase chips
│   │       │   └── ResourceGauge.tsx    # GPU%, VRAM, RAM, tps
│   │       └── store/
│   │           └── panelStore.ts    # Zustand store; hydrated by extension postMessage
│   │
│   └── config/
│       ├── defaults.ts             # Threshold constants
│       └── schema.ts               # Zod schema for extension settings
│
├── sidecar/
│   ├── main.py                     # JSON-RPC 2.0 over stdio — single entry point
│   ├── rag/
│   │   ├── chunker.py              # tree-sitter AST chunker (function/class boundaries)
│   │   ├── embedder.py             # sentence-transformers/all-MiniLM-L6-v2 on CPU
│   │   └── retriever.py            # FAISS query + BM25 re-rank
│   ├── monitor/
│   │   ├── gpu_monitor.py          # pynvml — temperature, VRAM, throttle state
│   │   └── ram_monitor.py          # psutil — available RAM
│   └── requirements.txt
│
├── test/
│   ├── unit/
│   └── integration/
│
└── AGENTS.md                       # Persistent state file — committed to git
```

---

## Core Architecture

### Process Topology

```
VS Code Extension Host (Node.js — never blocked)
├── MessageBus (EventEmitter3)
│   ├── StateMachine ──► WorkflowScheduler
│   ├── ContextBudget
│   └── CircuitBreaker
├── OllamaAdapter
│   └── http.request() stream → NDJSON parser → async generator
│       [Ollama daemon at localhost:11434 — GPU inference, separate process]
├── CloudAdapter (@anthropic-ai/sdk streaming)
├── SidecarAdapter
│   └── child_process.spawn("python sidecar/main.py")
│       [JSON-RPC 2.0 over stdio]
│       [Python sidecar: RAG index, GPU monitor — CPU-side, no VRAM]
└── DeepArchitectPanel (WebviewViewProvider)
    └── postMessage() / onDidReceiveMessage()
        [Webview: Preact + Zustand, retainContextWhenHidden: true]
```

**Isolation rule**: Extension host NEVER awaits on main thread. All Ollama calls use Node.js `http.request` streams piped to async generators consumed inside agents via `for await`. Sidecar calls are JSON-RPC with pending-map callbacks — non-blocking.

---

## Data Schemas

### AGENTS.md Format

Structured Markdown parsed by a hand-written 50-line section parser (H2 headers with `[bracket]` prefixes). This file is committed to git — it survives VS Code restarts, crashes, and context resets.

```markdown
# AGENTS.md — Deep-Architect Session State

## [Meta]
session_id: da-20260502-001
phase: III
model_local: qwen2.5-coder:14b
model_cloud: claude-opus-4-5
circuit_breaker_trips: 1
auto_escalate: true
require_phase_approval: true

## [Current State]
- Working on: AuthService.validateToken() — JWT expiry comparison
- Last tool: write_file(src/auth/AuthService.ts) — succeeded
- Test status: 2/5 passing
- Next immediate action: Fix Date.now() ms vs exp seconds mismatch

## [Lessons Learned]
- [2026-05-02T10:14Z] bcrypt.compare() is async — never use sync version in hot path
- [2026-05-02T11:05Z] Jest mock for Date.now() requires jest.spyOn, not manual override

## [Next Steps]
1. Fix validateToken() expiry logic
2. Write remaining 3 test cases for AuthService
3. Begin UserService implementation

## [Counterpoints Log]
- Approach A: Redis session storage
  - Counterpoint: Adds infra dependency; JWT stateless is simpler
  - Resolution: JWT 15min TTL + refresh token in HttpOnly cookie

## [Escalation Log]
- [2026-05-02T11:45Z] Reason: 3 consecutive test failures on validateToken()
  Resolution: Cloud identified off-by-one in Date.now()/exp comparison
```

### Session Config (per-session toggles in UI)

```typescript
interface SessionConfig {
  modelLocal: string;            // e.g. "qwen2.5-coder:14b"
  modelCloud: string;            // e.g. "claude-opus-4-5"
  autoEscalateToCloud: boolean;  // Configurable toggle — default false
  requirePhaseApproval: boolean; // Pause at Phase I→II, II→III transitions
  cloudBudgetCalls: number;      // Max cloud calls this session (default 20)
  thermalHardLimitC: number;     // Default 85°C
}
```

### ResourceSnapshot

```typescript
interface ResourceSnapshot {
  timestamp: number;
  gpu: {
    utilizationPercent: number;
    vramUsedMB: number;
    vramTotalMB: number;
    temperatureC: number;
    powerDrawW: number;
    throttled: boolean;
  };
  ram: { usedMB: number; totalMB: number; availableMB: number };
  ollamaTokensPerSecond: number;  // Rolling 10s average
}
```

---

## 4-Phase State Machine

### Phase Timings (9-hour budget)
```
Phase I   — Repository Mapping:     ~30 min
Phase II  — Brainstorming:          ~60 min  (pauses for approval if toggle on)
Phase III — Iterative Execution:   ~390 min
Phase IV  — Hardening:              ~60 min
```

### FSM Transition Table

| State | Event | Guard | Next State |
|---|---|---|---|
| `idle` | USER_START | workspace open | `I_mapping` |
| `I_mapping` | MAPPING_COMPLETE | index built | `II_brainstorm` |
| `I_mapping` | THERMAL_LIMIT | gpu.temp > hardLimit | `paused` |
| `II_brainstorm` | SYNTHESIS_READY | requirePhaseApproval=false | `III_execution` |
| `II_brainstorm` | USER_APPROVED | requirePhaseApproval=true | `III_execution` |
| `II_brainstorm` | TIMEOUT(60min) | auto-proceed if no approval needed | `III_execution` |
| `III_execution` | CIRCUIT_TRIPPED(human) | escalateTo==human | `paused` |
| `III_execution` | ALL_STEPS_COMPLETE | — | `IV_hardening` |
| `III_execution` | PHASE_TIMER(390min) | — | `IV_hardening` |
| `IV_hardening` | CHECKLIST_DONE | — | `complete` |
| `paused` | USER_RESUME | thermal OK | _previous_ |
| `paused` | THERMAL_OK | auto-resume enabled | _previous_ |
| `any` | USER_ABORT | — | `failed` |

### Phase I: Repository Mapping
1. Call `sidecar.rag.index({ workspacePath })` — tree-sitter parses all source files
2. Chunk at function/class/module boundaries (never mid-symbol); embed with `all-MiniLM-L6-v2` on CPU
3. Persist FAISS index to `.deep-architect/rag.faiss`
4. Write repo summary (file tree, languages, test framework, entry points) to AGENTS.md `[Current State]`
5. Watch `vscode.workspace.onDidChangeTextDocument` to invalidate changed file chunks

**VS Code APIs**: `vscode.workspace.findFiles()`, `vscode.workspace.fs.readFile()`, `vscode.workspace.onDidChangeTextDocument()`

### Phase II: Brainstorming / Counterpoint
Two Ollama threads run **sequentially** (RTX 3060 cannot run two large models in parallel):
- Thread A: "Architect" system prompt → generates approach
- Thread B: "Critic" system prompt → generates counterpoints (fresh context, adversarial framing)
- Thread A again: responds to counterpoints
- Synthesis prompt (larger model or cloud): produces final work plan

All exchanges written to AGENTS.md `[Counterpoints Log]`. Final plan written to `[Next Steps]`.

If `requirePhaseApproval=true`: workflow pauses, user sees synthesis in ChainOfThought panel, confirms or edits before Phase III begins.

### Phase III: Iterative Execution (TDD Loop)
```
1. Read next item from AGENTS.md [Next Steps]
2. RAG query: top-8 chunks relevant to current task
3. Build prompt: system + AGENTS.md state block (pinned) + RAG context + task + tool schema
4. Stream inference → parse tool calls from output (JSON block detection)
5. Execute tool calls via ToolRegistry
6. Run tests via TestRunnerTool
7. Pass → mark done, write lesson to AGENTS.md, advance
8. Fail → increment CircuitBreaker; at 3 → escalate (cloud or human per session config)
9. After resolution: reset CB failure count, continue
10. Write AGENTS.md [Current State] after every iteration
```

**Tool Schema** (JSON Schema sent in system prompt):
`read_file`, `write_file`, `run_terminal` (with timeout), `run_tests`, `search_codebase`, `update_agents_md`

### Phase IV: Hardening Checklist
1. Edge case pass — enumerate untested inputs, generate additional tests
2. Security scan — `npm audit` / `bandit`; model remediates critical/high
3. Documentation pass — JSDoc/docstring for all exported functions lacking it
4. Final AGENTS.md update — session summary, all lessons, final test counts
5. EpisodicLog sealed with session stats

---

## Circuit Breaker

### Failure Taxonomy
```typescript
type CircuitTripReason =
  | 'consecutive_test_failures'   // Same tests fail 3× after code changes
  | 'reasoning_loop_detected'     // Same 3-call sequence repeated 2× in last 20 calls
  | 'context_exhausted'          // Cannot prune further without losing state
  | 'ollama_crash'               // HTTP stream drops unexpectedly
  | 'tool_error_cascade'         // >3 tool errors in 10-minute window
  | 'thermal_halt';              // GPU temp forced pause (auto-resumes)
```

### Escalation Decision
```
reasoning_loop_detected → always Human (cloud may loop too)
context_exhausted       → always Human (task needs restructuring)
thermal_halt            → no escalation (auto-resume after cooldown)
all others              → Cloud if autoEscalateToCloud=true, else Human
```

### Loop Detection
Rolling 20-call history. Detect when last 3 calls === calls 3–6 positions prior (sequence repeat). Fires after 6 identical consecutive tool calls.

---

## Context Budget Management

### Token Counting
Approximate: `tokens ≈ chars / 3.5` for code (pessimistic = safe). For cloud calls, use `anthropic.messages.countTokens()` for exact counts before sending.

### ContextPruner Strategy (fires at 75% of `num_ctx`)
1. **Pinned** (never pruned): system prompt, AGENTS.md state block, last 4 turns
2. **Scored for pruning**: recency decay (half-life 20 turns) + lower score for tool results (already in AGENTS.md) + higher score for turns containing lessons/decisions
3. Drop lowest-scored entries until under 60% of budget
4. **Salvage**: extract lessons from dropped entries and append to AGENTS.md before discarding

AGENTS.md is always re-read from disk and injected fresh — context pruning never loses mission state.

### Dynamic `num_ctx` Scaling
| VRAM Free | `num_ctx` |
|---|---|
| < 1500 MB | 2048 |
| < 3000 MB | 4096 |
| < 5000 MB | 8192 (default) |
| ≥ 5000 MB | 16384 |

---

## Thermal Response Policy

| Condition | Response |
|---|---|
| GPU temp ≥ 85°C | Immediate pause, 120s auto-resume cooldown |
| GPU temp ≥ 80°C | 5s inter-request gap; reduce `num_ctx` to 75% |
| VRAM used > 90% | Force `num_ctx` = 4096 |
| RAM available < 4GB | Pause RAG indexing operations |

Monitored by Python sidecar (`pynvml` + `psutil`) polling every 10s, sent to extension host via JSON-RPC subscription event.

---

## Cloud Escalation Protocol

```
1. CircuitBreaker trips with non-human reason AND autoEscalateToCloud=true
2. Check CloudBudget: callsUsed < maxCallsPerSession (default 20)
3. Build escalation packet: { task, failedAttempts[-3], testOutput, relevantCode }
4. Stream to claude-opus-4-5 via @anthropic-ai/sdk; show [CLOUD] label in ChainOfThought
5. Apply cloud-proposed changes via ToolRegistry
6. Run tests: pass → reset CB, resume local model
7. Tests still fail → escalate to Human (vscode.window.showWarningMessage + panel notification)
8. CloudBudget exhausted → always escalate to Human regardless of config
```

**Cost guard**: Exponential backoff on 429s (1s → 2s → 4s → 8s → 16s with jitter).

---

## Agentic UI: Panel Layout

Registered as `WebviewViewProvider` in the primary sidebar (activity bar) — does not consume editor columns. `retainContextWhenHidden: true` — justified by panel being the primary UI.

```
┌──────────────────────────────────────────────────┐
│ DEEP-ARCHITECT          [Phase III] [⏸] [☁ off]  │
│ ●GPU 67% 71°C  ◆RAM 14.2/32GB  ⚡2.1 tps        │
├──────────────────────────────────────────────────┤
│ PHASE TIMELINE                                    │
│ ████████████░░░░░░░░░░ 3h 12m / 9h              │
│ [I✓] [II✓] [III ████░░] [IV pending]            │
├──────────────────────────────────────────────────┤
│ CHAIN OF THOUGHT (streaming)              [local] │
│ > Analyzing validateToken()...                    │
│ > Tool: read_file(src/auth/AuthService.ts)        │
│ > Found: Date.now() ms vs exp seconds mismatch   │
│ > Tool: write_file(src/auth/AuthService.ts)       │
│ > Tool: run_tests("auth") → ✓ 5/5 passing        │
├──────────────────────────────────────────────────┤
│ AGENTS.md VIEWER                      [Edit] [↻] │
│ Current: Fix validateToken() expiry logic        │
│ Next steps: 3 remaining                          │
│ Lessons: 4 entries                               │
├──────────────────────────────────────────────────┤
│ TOOL CALL LOG                            [clear]  │
│ 11:47:03  read_file   src/auth/…ts      12ms     │
│ 11:47:05  write_file  src/auth/…ts       8ms     │
│ 11:47:08  run_tests   auth              4.2s     │
└──────────────────────────────────────────────────┘
```

**Status bar** (3 right-aligned items): `[Phase III]` | `[local]`/`[☁ cloud]` | `[GPU 67% 71°C]` (turns warning color at 80°C).

**Session-start dialog**: Shows `SessionConfig` toggles before workflow begins — `autoEscalateToCloud`, `requirePhaseApproval`, model selection, cloud budget cap.

---

## Key Package Selections

### Extension Host (TypeScript)
| Concern | Package |
|---|---|
| Event bus | `eventemitter3` |
| Schema validation | `zod` |
| Cloud API | `@anthropic-ai/sdk` |
| Build | `esbuild` |
| Webview UI | `preact` + `htm` (no JSX transform, ~3KB) |
| Webview state | `zustand` |
| Tests | `vitest` |

**Excluded**: `langchain`, `llamaindex` (abstract away the Ollama `context` token management this design requires); full React (Preact is sufficient).

### Python Sidecar
| Concern | Package |
|---|---|
| AST parsing | `tree-sitter` + `tree-sitter-languages` |
| Embeddings | `sentence-transformers` (CPU, all-MiniLM-L6-v2) |
| Vector index | `faiss-cpu` |
| GPU monitoring | `pynvml` |
| System monitoring | `psutil` |
| Re-ranking | `rank-bm25` |

---

## Five Critical Files (build these first, in order)

1. **`src/core/StateMachine.ts`** — Phase FSM guards all agent transitions; bugs cascade everywhere
2. **`src/adapters/OllamaAdapter.ts`** — NDJSON stream + context token persistence; foundation of all local inference
3. **`src/core/CircuitBreaker.ts`** — Loop detection + escalation; prevents runaway 9-hour sessions
4. **`src/memory/AgentsFile.ts`** — AGENTS.md parser/writer; single source of persistent truth
5. **`sidecar/rag/chunker.py`** — AST chunk boundaries determine RAG quality for all 9 hours

---

## Implementation Phases (Suggested Order)

### Week 1 — Foundation
- [ ] Initialize `package.json` (VS Code extension manifest), `tsconfig.json`, `esbuild.config.js`
- [ ] Implement `MessageBus.ts` with typed event map
- [ ] Implement `OllamaAdapter.ts` — NDJSON streaming + context token store + model-agnostic config
- [ ] Resolve Technical Unknown #3: Ollama concurrent request behavior test on Windows
- [ ] Implement `SidecarAdapter.ts` — JSON-RPC 2.0 stdio IPC
- [ ] Write `sidecar/main.py` — JSON-RPC dispatcher skeleton

### Week 2 — Memory & RAG
- [ ] Implement `AgentsFile.ts` — section parser/writer
- [ ] Implement `EpisodicLog.ts` — append-only JSONL
- [ ] Write `sidecar/rag/chunker.py` — tree-sitter AST chunker for TS/JS + Python
- [ ] Write `sidecar/rag/embedder.py` + `retriever.py` — FAISS + BM25 re-rank
- [ ] Resolve Technical Unknown #1: Ollama context array stability test

### Week 3 — Core Orchestration
- [ ] Implement `StateMachine.ts` — 4-phase FSM
- [ ] Implement `CircuitBreaker.ts` — failure counters + loop detection
- [ ] Implement `WorkflowScheduler.ts` — thermal gating + inter-request pacing
- [ ] Implement `ContextBudget.ts` + `ContextPruner.ts`
- [ ] Resolve Technical Unknown #2: Extension host memory profiling session

### Week 4 — Agents & Tools
- [ ] Implement `ToolRegistry.ts` + all 5 tools (FileSystem, Terminal, Search, TestRunner + UpdateAgentsMd)
- [ ] Implement `RepositoryMappingAgent.ts` (Phase I)
- [ ] Implement `BrainstormAgent.ts` (Phase II — two-thread debate)
- [ ] Implement `ExecutionAgent.ts` (Phase III — TDD loop)
- [ ] Implement `HardeningAgent.ts` (Phase IV — checklist)

### Week 5 — UI & Cloud
- [ ] Implement `DeepArchitectPanel.ts` + `StatusBarManager.ts`
- [ ] Build webview components (Preact): ChainOfThought, AgentsViewer, ToolCallLog, PhaseTimeline, ResourceGauge
- [ ] Implement `CloudAdapter.ts` with cost guard + exponential backoff
- [ ] Implement `sidecar/monitor/gpu_monitor.py` + `ram_monitor.py`
- [ ] Wire session-start config dialog
- [ ] End-to-end test: full 1-hour compressed session on real project

---

## Verification Plan

1. **Unit tests** (`vitest`): CircuitBreaker loop detection, ContextPruner scoring, AgentsFile section parser, OllamaAdapter NDJSON parsing with mock streams
2. **Sidecar tests** (`pytest`): chunker produces no mid-symbol splits, retriever returns ranked results, GPU monitor handles pynvml exceptions gracefully
3. **Integration**: Connect to local Ollama with a small model (7b); run Phase I on the extension's own source directory; verify FAISS index written, AGENTS.md populated
4. **Marathon dry-run**: 1-hour compressed session (small task, frequent test cycles) with memory profiling enabled; verify EpisodicLog growth, context pruning fires correctly, no extension host OOM
5. **Circuit breaker drill**: Deliberately introduce a failing test; verify CB trips at failure 3, escalation notification appears, AGENTS.md checkpoint is intact after recovery
