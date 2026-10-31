# Skills library

Copies of the owner's own agent skills (folders with a `SKILL.md`), kept here so they are versioned and can be
reused by the stack's other clients. The repo's own Claude Code skills (`/retro`, `/why-routed`, `/brainstorm`,
`/harden`) stay in `.claude/skills/`; this folder is the collected library.

## How skills get here

```
uv run scripts/stack.py skills-sync             # copy new or changed skills
uv run scripts/stack.py skills-sync --dry-run   # only report
```

Rules live in [sync.yaml](sync.yaml):

- Sources: `~/.claude/skills/*` (personal Claude Code skills) and the claude.ai-synced bundle under
  `~/.claude/skills/synced/`, of which only skills you made yourself (manifest `source: plugin`) are copied.
- Never copied: Anthropic's skills (`anthropic`, `anthropic-example`), anything with `license: Proprietary`, and
  names in `exclude` (for example skills holding personal data; this repository is public).
- One way: a skill deleted at its source stays here and is reported as `orphaned`; remove it in a reviewed commit.
- `index.json` records where each skill came from.

A Claude Code desktop scheduled task (`skills-sync`, weekly) runs the sync in a temporary worktree off `main`, checks
new and changed content for personal data, and opens a pull request when something was added or modified. It never
merges. Its prompt is [sync-task-prompt.md](sync-task-prompt.md); setup steps are in
[docs/manuals/installation.md](../docs/manuals/installation.md), step 8.

Do not edit a synced skill here; edit it at its source and let the next sync bring it over.
