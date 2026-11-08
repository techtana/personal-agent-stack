# personal-agent-stack

**Direction (2026-10-26): private first.** Every request is to be processed by private models, on owned hardware
or confidential cloud VMs; external model APIs become an optional, explicit, gated user choice. The plans are in
[docs/plans/](docs/plans/README.md). Since 2026-10-26 the build routes every tier to local models, with or without an
API key; external models stay off until the privacy gate exists.

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
              local-fim · local-small · local-primary   (private only; external models off: policy/privacy.yaml)
              JSONL traces → traces/litellm/     OTLP → Phoenix :6006
                 │                                              │
      Ollama (native, GPU) :11434
      qwen2.5-coder:1.5b-base · qwen3.5:9b · qwen3.6:35b-a3b-coding (MoE, experts in RAM)

 Orchestrator MCP :8765  delegate/get_job/record_lesson   ·   hooks → traces/claude/   ·   nightly retro → PR
```

Design, decisions and measurements: [docs/ORCHESTRATOR-DESIGN.md](docs/ORCHESTRATOR-DESIGN.md).
Private-first multi-user plans (cloud-led on confidential VMs, local-led), privacy gate and installation:
[docs/plans/](docs/plans/README.md).
Stable rules for agents: [AGENTS.md](AGENTS.md). State and lessons: [memory/](memory/).
Manuals: [installation](docs/manuals/installation.md) · [choosing drives](docs/manuals/choosing-drives.md) ·
[user guide](docs/manuals/user-guide.md) · [troubleshooting](docs/manuals/troubleshooting.md).

**When to use it:** you write code with AI agents on your own GPU workstation, and you want routine work to stay
local, private and free. External models are off; they will only ever be an explicit, gated choice (docs/plans/).
It is not a team or hosted service yet.

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
# Windows: double-click install.cmd (or run .\scripts\setup.ps1). A window asks where the models and the
# Python tools go, then setup runs in the background: .env secrets, Ollama env, uv tools, configs, model downloads.
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

Clicking the icon opens a status window with three tabs (since 2026-10-27): **Overview** (services, start/stop, models
loaded in Ollama), **Usage** (requests, tokens, latency, tok/s and cost per model, from `traces/litellm/`) and
**Settings** (models, context sizes, tracing, Open WebUI, Ollama runtime; **Apply** saves to `machines/<HOST>.yaml`,
rebuilds and restarts what changed) and **Resources** (live CPU, RAM,
driver-reported GPU engine use and dedicated GPU memory per process; unavailable readings show as `-`). The icon is green when everything is up, amber when something is down, red when
the gateway or Ollama is down. The tray runs outside any terminal or Claude Code session, so its services keep running.
"Quit (keep services running)" closes only the tray; "Stop services and quit" stops everything.

After a quit, start it again from the Start menu entry **Agent Stack** (the installer creates it) or by double-clicking
`start.cmd` in the repository folder; either opens the window when the tray is already running. `stop.cmd` closes the
tray and stops its services (Ollama keeps running), even when the tray has already been quit.

For services that must run before anyone signs in (edge mode), register one Task Scheduler task per service instead,
from an elevated terminal: `uv run scripts/stack.py tasks install`. See the
[installation manual](docs/manuals/installation.md#run-the-services-before-sign-in-optional).

Then:

- **Claude Code on your subscription (default):** open this repo in Claude Code. The departments appear as
  subagents (`@security review src/auth.py`), `/retro`, `/harden`, `/brainstorm`, `/why-routed` as skills,
  `/ux-rules` for UX reviews against a researched rule catalog, `/claude-security-audit` for a privacy and safety
  check of your Claude setup, and the orchestrator as an MCP server (approve it once). Heavy work stays on your plan.
- **Claude Code on the local gateway:** `.\scripts\claude-local.ps1` (or `.sh`). A separate config dir
  (`~/.claude-local`) points at LiteLLM, so local models serve `sonnet`/`haiku` aliases and plan quota is untouched.
- **Open WebUI:** http://127.0.0.1:3000 -> create the admin user -> Workspace -> Models -> Import each
  `config/openwebui/<dept>.json`; Admin -> Integrations -> External Tool Servers -> MCP (Streamable HTTP)
  `http://127.0.0.1:8765/mcp` with `ORCHESTRATOR_BEARER` from `.env` as the bearer (not `WEBUI_SECRET_KEY`) and
  ID `personal-agent-stack`; the department models switch its tools on in new chats.
- **OpenCode:** `opencode.json` registers the gateway as provider `litellm`; agents are in `.opencode/agents/`.
- **Autocomplete in VS Code:** `config/continue/config.yaml` (Continue, autocomplete role only).

## Configuration

| Where | What |
|---|---|
| `machines/_defaults.yaml` | hardware classes -> model lineup, Ollama env, ports, service modes |
| `machines/<HOST>.yaml` | detected hardware + your overrides (`models.primary`, `model_store`) |
| `policy/privacy.yaml` | private-first policy: deployment location, `external.enabled` (off; the build refuses `true` until the privacy gate exists) |
| `agents/<id>.yaml` | one department: prompt, tools, Claude Code model alias, routing tiers, evals |
| `agents/_common.md` | working agreements appended to every department prompt |
| `.env` | `LITELLM_MASTER_KEY`, `ORCHESTRATOR_BEARER`, `WEBUI_SECRET_KEY`, `ANTHROPIC_API_KEY` (unused until external models exist) |
| `.claude/settings.json` | hooks (trace capture), permissions, gateway hint headers |
| `.claude/settings.local.json` | per-machine: MCP bearer env, `autoMemoryDirectory` -> `memory/claude/` |

After any change: `uv run scripts/stack.py build` (and `up`/`down` to restart the gateway).

## Cost model

- Autocomplete, embeddings, titles/summaries and the simple/medium tiers are local: $0.
- Every tier is local, with or without an API key in `.env` (private first, since 2026-10-26). External models will be
  explicit aliases behind the privacy gate, never a tier or fallback (docs/plans/SHARED-COMPONENTS.md section 2).
- Interactive Claude Code on the subscription costs no API dollars; a credential variable (profile B or
  an API key in the gateway) bills per token. Traces record cost per request; `retro` reports cost per department.

## Commands

```
uv run scripts/stack.py doctor [--write-profile [--refresh]]   hardware, tools, ports, chosen class
uv run scripts/stack.py profile | build | setup | pull [--all]
uv run scripts/stack.py up [svc...] | down [svc...] | status
uv run scripts/stack.py tray [--show | --foreground | --status | --stop | --install-startup | --remove-startup]
uv run scripts/stack.py tasks install|remove|start|stop|status|xml [svc...] [--trigger startup|logon]
uv run scripts/stack.py bench [--model m] [--num-ctx n] [--tokens n] [--runs n]
uv run scripts/stack.py smoke [--dept id] [--skip-mcp] [--media | --media-only]
uv run scripts/stack.py media check|install|provision          ComfyUI and image models under media.root (path guard first)
uv run scripts/stack.py media gpu chat|media                   hand the GPU to chat (free ComfyUI) or media (unload Ollama)
uv run scripts/stack.py dictate install|start|stop|status|check voice typing in any app: Ctrl+Alt+D or the mic button; Ctrl+Alt+R or the pencil button refines selected text
uv run scripts/stack.py dictate transcribe note.wav [--style concise]   the voice typing pipeline on a recording
uv run scripts/stack.py why-routed [--last n] [--days n]
uv run scripts/stack.py retro -- --days 7 [--reflect local-small|none] [--pr]
uv run scripts/stack.py skills-sync [--dry-run]                 copy your own skills into skills/ (rules: skills/sync.yaml)
npx promptfoo@0.125.0 eval -c evals/<dept>/promptfooconfig.yaml --repeat 3
```

## Troubleshooting

See [docs/manuals/troubleshooting.md](docs/manuals/troubleshooting.md): health checks, log locations and a
symptom → cause → fix table. Logs are in `.run/logs/<service>.log`; Ollama's is `%LOCALAPPDATA%\Ollama\server.log`.

## Assumptions and limitations

- It is built for one developer on one workstation. Every service listens on 127.0.0.1 only, and nothing is multi-user.
- It needs an NVIDIA GPU with at least 8 GB of VRAM. On 32 GB of RAM, the 35B MoE decodes at about 25 tok/s,
  against about 52 for the dense 9B (SEKAIHOME, 2026-10-25).
- Only Windows is verified (2026-10-26). Service management on Linux and macOS is written but untested, and so is the Docker compose path.
- Cloud tiers have not been exercised yet, because no API key is on the reference machine. Claude Code profile B has
  not been run as a live session yet. Since 2026-10-28 the build is private only, so no tier can reach an external
  model at all (`policy/privacy.yaml`, `external.enabled: false`).
- AI agents on the machine run as the owner's own account, so nothing at the operating-system level stops them reading
  personal files. A plan to fix that exists ([AGENT-FILE-ISOLATION.md](docs/plans/AGENT-FILE-ISOLATION.md)); nothing
  is applied yet.
- Routing budgets and LiteLLM's adaptive router need Postgres, so they are not in use.

## Known issues

Tracker: this repository's GitHub issues.

- Phoenix does not start on SEKAIHOME since 2026-10-26: Smart App Control blocks compiled modules in its tool
  environment (pyarrow, sqlalchemy, pandas). The plans remove Phoenix; until then turn **Phoenix tracing** off in the
  tray's Settings tab. The tray's Usage tab reads the JSONL traces and does not need Phoenix.
- Smart App Control may also start blocking the uv tool environments' `python.exe` (see the open items in `memory/state.md`).
- The LiteLLM admin UI (`/ui`, the tray's **Open gateway admin** link) shows "Not connected to DB!" because it needs Postgres.
- Images (2026-11-04): Smart App Control refused PyAV 19.0.2 and 16.0.1 inside ComfyUI's environment; 17.0.0 runs,
  so setup pins `av==17.0.0` (`media.SAC_PINS`). A future refusal shows as "An Application Control policy has blocked
  this file" in `.run/logs/comfyui.log`.
- Vision, speech, the Auto router, style transfer, video with audio, music and web search from the multimodal plan
  are not built yet (docs/design/plans/2026-11-01-multimodal-stack.md).
- `local-reviewer` points at `flint:40b-a2b`, which is not pulled. No tier routes to it.
- A chat message cannot switch models. Open WebUI sends each message to the model picked in the chat's model list
  (or with `@` in the input box), and `local-primary` is always the local model.
- `/ux-rules` lives in `.claude/skills/ux-rules/`, not in the `skills/` library. The commit that moves it (`a8400c9`)
  landed on the PR branch after PR #13 merged (2026-11-01).
- D: on SEKAIHOME is exFAT, which has no file permissions, so any account can read everything on it (found
  2026-10-30). Personal data there must move, or the drive must be reformatted to NTFS, before the agent account split
  can protect it.
- An empty Open WebUI database (`litellm.db`, `litellm.db-shm`, `litellm.db-wal`) has been committed at the repository
  root since 2026-10-26 (`d93211b`). Its tables hold no rows; it is not used by the stack.
- The Claude Code hook log (`scripts/hooks/log_turn.py`, `traces/claude/`) keeps the first 200 characters of the last
  assistant message and the first 300 characters of each Bash command, although its docstring says no prompt or file
  contents are stored (found 2026-11-01).

## Path forward

Running list. Add new items; don't rewrite old ones.

- 2026-10-27: elevated steps from B-S0/B2b: `winget configure --enable`, then `stack.py tasks install --trigger startup`
  once B2 lands.
- 2026-10-27: apply `winget/configuration.winget` on a clean Windows account (B3).
- 2026-10-27: remove Phoenix from the stack (plan item R); it no longer starts on SEKAIHOME.
- 2026-10-26: tray app design, plus CPU, RAM and GPU use per process (#4). Design and usage done 2026-10-27 (PR #9);
  the per-process view (Resources tab) landed with PR #8.
- 2026-10-25: confirm that the tray and its services start on their own after a reboot.
- 2026-10-25: Open WebUI first run (admin user, model import, MCP server).
- 2026-10-25: add `ANTHROPIC_API_KEY` and verify the cloud tiers. (Superseded 2026-10-26: private first, no cloud tiers.)
- 2026-10-25: run `scripts/claude-local.ps1` end to end on the 9B at 32k.
- 2026-10-25: try the 35B as primary again after a RAM upgrade; try tuning `LLAMA_ARG_N_CPU_MOE`.
- 2026-10-25: first `/retro` after a week of real traces; wire up the Open WebUI thumbs export.
- 2026-10-25: test service management on Linux and macOS.
- 2026-10-26: build is private only (S6/B1 core): no automatic cloud tiers. Next: privacy gate S1/S2, guardrail S3,
  evals S8, then B2 services, R removals and the `stack.py install` installer (B3). Merged to `main` 2026-10-28 (PR #8).
- 2026-10-31: create the weekly `skills-sync` scheduled task from `skills/sync-task-prompt.md` and click **Run now** once.
- 2026-11-01: hard block on AI agents reading personal files: decide D1-D4, deal with the exFAT D: drive, finish the
  V-F checks, then build `stack.py isolate` (I2) ([plan](docs/plans/AGENT-FILE-ISOLATION.md)).
- 2026-11-01: merge `a8400c9` to move `/ux-rules` into `skills/`; run the second `ux-rules` eval round with the
  sharper assertions.
- 2026-11-01: remove the stray `litellm.db*` files from the repository root and ignore them.
- 2026-11-01: multimodal stack (vision, speech, images, style transfer, video with audio, music, web search, routing
  per message): plan proposed, nothing built. Start from [docs/HANDOFF-2026-11-01-multimodal.md](docs/HANDOFF-2026-11-01-multimodal.md).

## Design decisions

Running log of the most important decisions. Never delete an entry; mark a reversed one as superseded. The full log,
with reasons and rejected alternatives, is [docs/design/DECISIONS.md](docs/design/DECISIONS.md); plans and their status
are indexed in [docs/design/](docs/design/README.md).

- 2026-10-24: Compose existing tools (Claude Code, OpenCode, LiteLLM) instead of building a custom harness. A
  hand-rolled proxy broke tool-using clients.
- 2026-10-24: Run Ollama and every service natively, with no Docker or WSL2, which would reserve RAM the MoE needs.
- 2026-10-24: Ollama is the only local inference engine, because it already runs llama-server with MoE-aware placement.
- 2026-10-24: Define each department once in `agents/*.yaml` and generate every tool's files from it. Duplicated prompts drifted.
- 2026-10-24: Self-improvement is a human-gated PR loop with an eval gate. Nothing merges automatically.
- 2026-10-24: Name the orchestrator secret `ORCHESTRATOR_BEARER`, because Claude Code blanks `*_TOKEN` and `*_API_KEY` in `.mcp.json`.
- 2026-10-25: Make SEKAIHOME's primary `qwen3.5:9b` at 32k instead of the 35B MoE: twice the decode speed and
  about 17 GB of RAM left free.
- 2026-10-25: Local tiers that share a model use the same `num_ctx` and load options, so Ollama never reloads between them.
- 2026-10-25: Start uv tools through their environment's `python.exe`, because Smart App Control blocked the `~/.local/bin` launchers.
- 2026-10-25: Identify a service by pid plus process start time, because Windows reuses pids.
- 2026-10-25: Starting services with `CREATE_BREAKAWAY_FROM_JOB` from an agent shell (superseded the same day; it
  was unreliable). The tray app launched through Explorer now owns the services.
- 2026-10-26: Private first. External model APIs are off at install and become an explicit, gated user choice. This
  supersedes automatic cloud tiers.
- 2026-10-26: Build the privacy plans on existing open-source tools (Presidio, detect-secrets, deface, ExifTool,
  Keycloak/Authentik) and write only glue.
- 2026-10-26: Edge mode runs each service under a Task Scheduler task with a 2-minute watchdog trigger, because Task
  Scheduler's restart on failure does not restart a killed process.
- 2026-10-26: Windows dependencies come from a generated winget configuration file, so the install is unattended and reviewable.
- 2026-10-27: The tray's Settings tab edits `machines/<HOST>.yaml` and restarts only what changed; cloud tiers stay
  read-only there, because turning them on is a deliberate `.env` decision.
- 2026-10-28: The private-only build is on `main` (PR #8): a tier, fallback, default or profile B alias that names an
  external model fails the build.
- 2026-10-29: Proposed, not decided: block AI agents from personal files with a separate standard Windows account and
  NTFS deny entries, because every agent's own settings are advisory on native Windows.
- 2026-10-31: Version the owner's own skills in `skills/` with a one-way `skills-sync`; never sync Anthropic's,
  proprietary or personal-data skills, because the repository is public.
- 2026-11-01: UX reviews use `/ux-rules`, a catalog of 122 researched rules with evidence grades; it will not help
  A/B-test deceptive patterns.

## Background knowledge

The stack rests on a few domains a newcomer may not know: how local models use GPU memory, how a gateway routes
requests, how privacy is enforced rather than advised, how Windows keeps background services alive, and how coding
agents improve from traces. Start with [docs/knowledge/README.md](docs/knowledge/README.md), which gives a reading
order and a glossary.

## Repository layout

```
agents/            department source of truth (+ _common.md)        machines/   hardware profiles
scripts/           stack.py CLI, stacklib/, tray.py, retro.py, hooks/   orchestrator/  FastMCP server + job store
winget/            configuration.winget, configuration.edge.winget (generated by `stack.py build`)
infrastructure/    litellm/ (config.yaml generated, custom_callbacks.py), docker-compose.yml (optional)
.claude/           settings, skills (retro, harden, brainstorm, why-routed, ux-rules, claude-security-audit), agents/ (generated)
skills/            your own skills library, synced weekly by a scheduled task (README, sync.yaml, sync-task-prompt.md)
.opencode/ opencode.json  config/openwebui/ config/continue/   evals/ (generated gates)   memory/   traces/   retro/
docs/              ORCHESTRATOR-DESIGN.md, manuals/, plans/ (private-first plans), design/ (decision log, plan index),
                   knowledge/ (domain background for newcomers), decisions/ (ADRs), research/, archive/,
                   HANDOFF-2026-10-24.md
```
