# AGENTS.md - personal-agent-stack

Private-first agent stack: Ollama on owned GPUs (or confidential cloud VMs), a LiteLLM gateway with a local privacy
gate, Open WebUI as the user surface, Claude Code as the owner's development tool, and a human-gated retrospective
that improves prompts and routing from traces. External model APIs are optional, explicit and gated
(`docs/plans/`). Stable instructions live here; mutable state
is in `memory/state.md`; durable lessons in `memory/lessons.md`; the design in `docs/ORCHESTRATOR-DESIGN.md`.

## Departments

`app-dev`, `testing`, `security`, `devops`, `code-review`, `docs`. Each is defined once in
`agents/<id>.yaml` and generated into every surface by `uv run scripts/stack.py build`:

- Claude Code: `.claude/agents/<id>.md` (mention `@<id>`, let Claude delegate, or `claude --agent <id>`).
- Gateway: model `<id>` (complexity router over private local deployments only), `<id>-local`. External models
  are off (`policy/privacy.yaml`); the build fails if a tier, fallback or default names a non-private deployment.
- OpenCode: `.opencode/agents/<id>.md`; Open WebUI: import `config/openwebui/<id>.json`.
- Orchestrator MCP (`.mcp.json`): `delegate(department, task, tier)` returns a job handle; `get_job`, `record_lesson`.

## Rules for agents working in this repo

1. Never edit generated files (`.claude/agents/*.md`, `.opencode/agents/*.md`, `config/openwebui/*.json`,
   `evals/*/promptfooconfig.yaml`, `evals/*/prompt.json`, `infrastructure/litellm/config.yaml`, `winget/*.winget`). Edit
   `agents/*.yaml`, `machines/*.yaml` or `agents/_common.md`, then run `uv run scripts/stack.py build`.
2. Hardware-dependent values (models, context sizes, Ollama env, ports) come from `machines/<HOST>.yaml`
   plus `machines/_defaults.yaml`. Adding a machine = `uv run scripts/stack.py doctor --write-profile` on it.
3. Never pass `temperature`, `top_p` or `top_k` to Anthropic models (HTTP 400 since 2026-10-21). Local
   deployments may set them under `local:` in the agent YAML.
4. Secrets live only in `.env` (gitignored) and `.claude/settings.local.json`; `.mcp.json` reads
   `${ORCHESTRATOR_BEARER}` (a name Claude Code does not blank).
5. Work in bounded tasks with human checkpoints. Say `ESCALATE: <reason>` when stuck twice.
6. Append lessons as dated bullets to `memory/lessons.md` (or via the orchestrator `record_lesson` tool);
   never rewrite earlier bullets. Record measurements and open items in `memory/state.md`.
7. Python code runs through `uv run` (see `pyproject.toml`); gateway, Phoenix and Open WebUI are `uv tool`
   installs, not project dependencies. Keep scripts cross-platform (PowerShell + bash wrappers call Python).
8. Commit messages: conventional prefix (`feat:`, `fix:`, `docs:`, `retro:`), imperative, one topic.
9. Private first: never put an external model in a router tier, fallback, default, task or embedding alias; external
   models are explicit aliases behind the privacy gate (`docs/plans/SHARED-COMPONENTS.md` section 2). Do not build
   privacy skills, hooks or MCP add-ons for clients outside the privacy boundary (Claude Code profile A, Claude
   Desktop): they can only advise and would imply enforcement that does not exist.

## Everyday commands

```
uv run scripts/stack.py tray                      # tray app: runs the services; window shows status, usage per model, settings
uv run scripts/stack.py status | up | down        # native services (phoenix, litellm, orchestrator, open_webui)
uv run scripts/stack.py tasks install|status|stop # edge mode: one Task Scheduler task per service (install: elevated)
uv run scripts/stack.py smoke                     # gateway + MCP end-to-end checks
uv run scripts/stack.py bench                     # tok/s and GPU/CPU split of the primary local model
uv run scripts/stack.py why-routed --last 20      # routing decisions from traces
uv run scripts/stack.py retro --days 7            # retrospective report (then /retro in Claude Code)
scripts/claude-local.ps1 | .sh                    # Claude Code on the local gateway (profile B)
```
