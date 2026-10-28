# Department agents (single source of truth)

Each `agents/<id>.yaml` defines one department once. `uv run scripts/stack.py build` generates:

| Output | Consumer |
|---|---|
| `.claude/agents/<id>.md` | Claude Code subagents (`@<id>` or auto-delegation; `claude --agent <id>`) |
| `.opencode/agents/<id>.md` + `opencode.json` models | OpenCode |
| `config/openwebui/<id>.json` | Open WebUI Workspace > Models > Import |
| `infrastructure/litellm/config.yaml` | LiteLLM model `<id>` (complexity router over private deployments), `<id>-local` |
| `evals/<id>/promptfooconfig.yaml` | promptfoo regression gate |

Never edit generated files; edit the YAML and rebuild. `agents/_common.md` is appended to every
system prompt.

## Fields

```yaml
id: app-dev                 # also the model alias on the gateway and the subagent name
name: App Developer
color: blue                 # Claude Code subagent color
description: >-             # one paragraph; drives Claude Code auto-delegation and Open WebUI
tools: [Read, Grep, Glob, Edit, Write, Bash]   # Claude Code tools (omit = inherit all)
claude:
  model: sonnet             # haiku | sonnet | opus (subscription profile aliases)
  permission_mode: acceptEdits
  max_turns: 50
  memory: project           # .claude/agent-memory/<id>/
  effort: medium
routing:                    # LiteLLM complexity_router tiers (lowercase here, upper-case in config)
  simple: local-primary
  medium: local-primary
  complex: local-primary
  reasoning: local-primary
  plan_mode_min_tier: complex
  keyword_tier_rules:
    - {keywords: ["threat model"], tier: reasoning}
local:
  temperature: 0.2          # applied ONLY to local deployments
opencode:
  mode: subagent
  permission: {edit: allow, bash: ask}
openwebui:
  suggestion_prompts: ["..."]
system_prompt: |
  ...
evals:
  - name: ...
    prompt: ...
    assert:
      - {type: icontains, value: ...}
```

Tier targets are private deployments only: `local-small`, `local-primary`, `local-reviewer`. Any other target fails
the build (private first; external models are explicit aliases, never tiers: `policy/privacy.yaml`). A target this
machine does not serve is rewritten to its best local deployment at build time.
