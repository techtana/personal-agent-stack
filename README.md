# personal-agent-stack

A local-first coding-agent stack for one developer on one GPU workstation, composed from open-source
tools rather than a custom harness. Six department agents (app-dev, testing, security, devops,
code-review, docs) are defined once and generated into Claude Code, OpenCode, Open WebUI and a LiteLLM
gateway that routes each request to the cheapest tier that can do the job: a small always-resident
model for autocomplete, a mixture-of-experts coder on the local GPU for routine work, and Claude
Haiku/Sonnet/Opus 5.5 through the gateway only when complexity, context size or a stall demands it.

```
 Claude Code (terminal / VS Code / desktop)   OpenCode   Open WebUI (chat, thumbs)   promptfoo (evals)
            │ Anthropic /v1/messages              │ OpenAI /v1       │                     │
            └──────────────┬──────────────────────┴──────────────────┴─────────────────────┘
                           ▼
            LiteLLM gateway :4000  (one model alias per department = complexity router)
              local-fim · local-small · local-primary · [cloud-cheap · cloud-default · cloud-heavy]
              JSONL traces → traces/litellm/     OTLP → Phoenix :6006
                 │                                              │
      Ollama (native, GPU) :11434                   Anthropic API (only with ANTHROPIC_API_KEY)
      qwen2.5-coder:1.5b-base · qwen3.5:9b · qwen3.6:35b-a3b-coding (MoE, experts in RAM)

 Orchestrator MCP :8765  delegate/get_job/record_lesson   ·   hooks → traces/claude/   ·   nightly retro → PR
```

Design, decisions and measurements: [docs/ORCHESTRATOR-DESIGN.md](docs/ORCHESTRATOR-DESIGN.md).
Stable rules for agents: [AGENTS.md](AGENTS.md). State and lessons: [memory/](memory/).

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| NVIDIA GPU | 12 GB VRAM for the default lineup; 8 GB works with the `small-gpu` class | 32 GB system RAM enables the MoE primary; 16 GB falls back to a dense 9B |
| [uv](https://docs.astral.sh/uv/) | 0.12+ | the only hard requirement; it fetches Python 3.11/3.12 and the tools |
| [Ollama](https://ollama.com/download) | 0.40+ | native install (Windows: `winget install --id Ollama.Ollama`); not in Docker |
| Claude Code | 2.1.293+ | `winget install --id Anthropic.ClaudeCode` or the VS Code extension / desktop app |
| Node | 24+ | only for `npx promptfoo` evals |

Docker is optional (`infrastructure/docker-compose.yml`); the reference machine runs everything natively.

## Quick start

```powershell
# Windows (PowerShell)
.\scripts\setup.ps1          # detect hardware -> machines/<HOST>.yaml, write .env secrets, set Ollama env,
                             # install litellm/phoenix/open-webui as uv tools, generate configs, pull models
uv run scripts/stack.py up   # start phoenix, litellm, orchestrator, open_webui
uv run scripts/stack.py smoke
```

```bash
# Linux / macOS / WSL / Git Bash
./scripts/setup.sh && uv run scripts/stack.py up && uv run scripts/stack.py smoke
```

To keep the stack running in the background, use the tray app instead of `up`:

```
uv run scripts/stack.py tray                    # starts the services and a tray icon (Windows: under the ^ hidden icons)
uv run scripts/stack.py tray --install-startup  # optional: start the tray at login
```

Clicking the icon opens a status window: each service's state, Open buttons for Open WebUI, Phoenix and the LiteLLM
admin UI, and start/stop controls. The icon is green when everything is up, amber when something is down, red when the
gateway or Ollama is down. The tray runs outside any terminal or Claude Code session, so its services keep running.
The window also shows input/output token totals, average operation times per process and model, and cloud cost for a
selectable period (1 hour, 24 hours, 7 days, 30 days, or all time). Metrics cover requests routed through LiteLLM;
direct Claude subscription sessions bypass this telemetry. Ollama timings provide local model-load, prompt-evaluation,
and generation phases when reported; cloud providers expose request duration only. Phoenix receives corresponding
operation spans for inspection and aggregation. "Quit (keep services running)" closes only the tray; "Stop services and quit" stops everything.

Then:

- **Claude Code on your subscription (default):** open this repo in Claude Code. The departments appear as
  subagents (`@security review src/auth.py`), `/retro`, `/harden`, `/brainstorm`, `/why-routed` as skills,
  and the orchestrator as an MCP server (approve it once). Heavy work stays on your plan.
- **Claude Code on the local gateway:** `.\scripts\claude-local.ps1` (or `.sh`). A separate config dir
  (`~/.claude-local`) points at LiteLLM, so local models serve `sonnet`/`haiku` aliases and plan quota is untouched.
- **Open WebUI:** http://127.0.0.1:3000 -> create the admin user -> Workspace -> Models -> Import each
  `config/openwebui/<dept>.json`; Admin -> Integrations -> External Tool Servers -> MCP (Streamable HTTP)
  `http://127.0.0.1:8765/mcp` with the bearer from `.env`.
- **OpenCode:** `opencode.json` registers the gateway as provider `litellm`; agents are in `.opencode/agents/`.
- **Autocomplete in VS Code:** `config/continue/config.yaml` (Continue, autocomplete role only).

## Configuration

| Where | What |
|---|---|
| `machines/_defaults.yaml` | hardware classes -> model lineup, Ollama env, ports, service modes, cloud model IDs |
| `machines/<HOST>.yaml` | detected hardware + your overrides (`models.primary`, `model_store`, `cloud.enabled`) |
| `agents/<id>.yaml` | one department: prompt, tools, Claude Code model alias, routing tiers, evals |
| `agents/_common.md` | working agreements appended to every department prompt |
| `.env` | `LITELLM_MASTER_KEY`, `ORCHESTRATOR_BEARER`, `WEBUI_SECRET_KEY`, optional `ANTHROPIC_API_KEY` |
| `.claude/settings.json` | hooks (trace capture), permissions, gateway hint headers |
| `.claude/settings.local.json` | per-machine: MCP bearer env, `autoMemoryDirectory` -> `memory/claude/` |

After any change: `uv run scripts/stack.py build` (and `up`/`down` to restart the gateway).

## Cost model

- Autocomplete, embeddings, titles/summaries and the simple/medium tiers are local: $0.
- With no API key, every tier is local. Adding `ANTHROPIC_API_KEY` turns on `cloud-cheap`
  (Haiku 5.5, $0.10/$0.50 per MTok), `cloud-default` (Sonnet 5.5, $2/$10) and `cloud-heavy`
  (Opus 5.5, $4/$20) for the complex/reasoning tiers, stalls and over-long contexts.
- Interactive Claude Code on the subscription costs no API dollars; a credential variable (profile B or
  an API key in the gateway) bills per token. Traces record cost per request; `retro` reports cost per department.

## Commands

```
uv run scripts/stack.py doctor [--write-profile [--refresh]]   hardware, tools, ports, chosen class
uv run scripts/stack.py profile | build | setup | pull [--all]
uv run scripts/stack.py up [svc...] | down [svc...] | status
uv run scripts/stack.py bench [--model m] [--num-ctx n] [--tokens n] [--runs n]
uv run scripts/stack.py smoke [--dept id] [--skip-mcp]
uv run scripts/stack.py why-routed [--last n] [--days n]
uv run scripts/stack.py retro -- --days 7 [--reflect cloud-cheap] [--pr]
npx promptfoo@0.125.0 eval -c evals/<dept>/promptfooconfig.yaml --repeat 3
```

## Troubleshooting

- `ollama ps` shows `PROCESSOR` with a large CPU share or `stack.py bench` is slow: the MoE experts live
  in RAM by design; if decode is far below the benchmark in `memory/state.md`, try `LLAMA_ARG_N_CPU_MOE=<n>`
  in `machines/<HOST>.yaml:ollama_env` (passed through to llama-server) and rerun `setup`.
- Gateway 401: clients must send the `LITELLM_MASTER_KEY` from `.env` as a Bearer token.
- Cloud tier never used: `ANTHROPIC_API_KEY` is empty, so the build rewrote cloud tiers to local; add the key and rebuild.
- Claude Code does not show the orchestrator: approve the project `.mcp.json` server when prompted, or set
  `enabledMcpjsonServers` (setup writes it to `.claude/settings.local.json`).
- Logs: `.run/logs/<service>.log`; Ollama: `%LOCALAPPDATA%\Ollama\server.log`.

## Repository layout

```
agents/            department source of truth (+ _common.md)        machines/   hardware profiles
scripts/           stack.py CLI, stacklib/, retro.py, hooks/        orchestrator/  FastMCP server + job store
infrastructure/    litellm/config.yaml (generated), custom_callbacks.py, docker-compose.yml (optional)
.claude/           settings, skills (retro, harden, brainstorm, why-routed), agents/ (generated)
.opencode/ opencode.json  config/openwebui/ config/continue/   evals/ (generated gates)   memory/   traces/   retro/
docs/              ORCHESTRATOR-DESIGN.md, HANDOFF-2026-10-24.md, research/, archive/DESIGN-2025.md, decisions/
```
