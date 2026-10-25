# AGENTS.md - personal-agent-stack

Local-first coding-agent stack for one developer: Ollama on the GPU, a LiteLLM gateway that routes each
department between local and cloud tiers, Claude Code as the primary agent surface, and a human-gated
retrospective that improves prompts and routing from traces. Stable instructions live here; mutable state
is in `memory/state.md`; durable lessons in `memory/lessons.md`; the design in `docs/ORCHESTRATOR-DESIGN.md`.

## Departments

`app-dev`, `testing`, `security`, `devops`, `code-review`, `docs`. Each is defined once in
`agents/<id>.yaml` and generated into every surface by `uv run scripts/stack.py build`:

- Claude Code: `.claude/agents/<id>.md` (mention `@<id>`, let Claude delegate, or `claude --agent <id>`).
- Gateway: model `<id>` (complexity router: local for simple/medium, cloud for complex/reasoning when an
  API key exists), `<id>-local`, `<id>-cloud`.
- OpenCode: `.opencode/agents/<id>.md`; Open WebUI: import `config/openwebui/<id>.json`.
- Orchestrator MCP (`.mcp.json`): `delegate(department, task, tier)` returns a job handle; `get_job`, `record_lesson`.

## Rules for agents working in this repo

1. Never edit generated files (`.claude/agents/*.md`, `.opencode/agents/*.md`, `config/openwebui/*.json`,
   `evals/*/promptfooconfig.yaml`, `evals/*/prompt.json`, `infrastructure/litellm/config.yaml`). Edit
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

## Everyday commands

```
uv run scripts/stack.py status | up | down        # native services (phoenix, litellm, orchestrator, open_webui)
uv run scripts/stack.py smoke                     # gateway + MCP end-to-end checks
uv run scripts/stack.py bench                     # tok/s and GPU/CPU split of the primary local model
uv run scripts/stack.py why-routed --last 20      # routing decisions from traces
uv run scripts/stack.py retro --days 7            # retrospective report (then /retro in Claude Code)
scripts/claude-local.ps1 | .sh                    # Claude Code on the local gateway (profile B)
```
