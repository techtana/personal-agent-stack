**Status:** done 2026-10-31 (PR #11); the weekly scheduled
task is not created yet (open item 12 in `memory/state.md`).

# Skills library and `skills-sync`

Reconstructed from the PR #11 description; no separate plan file was written.

## Goal

Keep the owner's own agent skills (folders with a `SKILL.md`) versioned in this repository, so they survive machine
changes and the stack's other clients can reuse them.

## Approach

- A `skills/` folder holds the copies. The repo's own Claude Code skills (`/retro`, `/why-routed`, `/brainstorm`,
  `/harden`) stay in `.claude/skills/`.
- `uv run scripts/stack.py skills-sync [--dry-run]` copies new skills and replaces changed ones. It compares each
  file's sha256 with line endings ignored, so a CRLF checkout does not count as a change.
- Rules live in `skills/sync.yaml`: the source folders, which claude.ai-synced skills qualify (manifest
  `source: plugin`), and an `exclude` list.
- Never copied: Anthropic's skills, skills with `license: Proprietary`, and excluded names. `job-search-agent` is
  excluded because it holds personal data and this repository is public.
- One way only: a skill deleted at its source is reported as `orphaned` and stays until a reviewed commit removes it.
- `skills/index.json` records where each skill came from.

## Phases

1. Command, rules file and tests (`tests/test_skills_sync.py`). Done in PR #11.
2. A weekly Claude desktop scheduled task (prompt in `skills/sync-task-prompt.md`): run the sync in a throwaway
   worktree off `main`, check new content for personal data, run the tests, open a pull request, never merge. Not
   created yet; it needed the command on `main` first.

## Outcome

- 2026-11-01: the next skill made after this, `ux-rules`, was meant to live in `skills/`, but the commit moving it
  there landed after its PR merged; on `main` it is still in `.claude/skills/` (see `DECISIONS.md`, 2026-11-01).
