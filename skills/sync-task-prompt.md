# Scheduled task: skills-sync

Paste everything below the line into a new Claude Code desktop scheduled task (see
[docs/manuals/installation.md](../docs/manuals/installation.md), step 8).

- Task name: `skills-sync`
- Schedule: weekly, Monday 09:00 (cron `0 9 * * 1`)
- Folder: `C:\Code\personal-agent-stack`

---

Sync the owner's personal agent skills into the personal-agent-stack repository: copy skills that are new AND update skills that were modified at their source, then open a pull request when anything changed. The repository is PUBLIC on GitHub (techtana/personal-agent-stack), so nothing personal may reach it.

Steps (Git Bash; main checkout is C:\Code\personal-agent-stack — do NOT edit, stash or switch branches in it):

1. `cd /c/Code/personal-agent-stack && git fetch origin main`.
   If `git show origin/main:scripts/stacklib/skills_sync.py` fails, the sync tool is not merged yet: report "skills-sync not on main yet" and stop.
2. If an open PR from a `skills/sync-*` branch already exists (`gh pr list --state open --search "head:skills/sync-"`), report its link and stop, so sync PRs don't pile up; the owner merges or closes it first.
3. Make a throwaway worktree off origin/main: `git worktree add -b skills/sync-$(date +%F) .claude/worktrees/skills-sync-$(date +%F) origin/main` and work only inside it.
4. In that worktree run `uv run scripts/stack.py skills-sync --dry-run`, then `uv run scripts/stack.py skills-sync`. The command compares every file of every allowed skill (sha256) with the copy in skills/:
   - `added`: a skill not yet in skills/ is copied in.
   - `updated`: a skill whose files differ from the repo copy (edited, added or removed files) replaces the repo copy completely.
   - `unchanged`: identical, nothing written.
   - `orphaned`: in skills/ but no longer at any source (deleted or renamed). Do not delete it; list it in the report. If an orphan looks like a rename of a newly added skill (similar SKILL.md body), say so.
   Sources and rules are in skills/sync.yaml (~/.claude/skills plus owner-made claude.ai skills; Anthropic's and proprietary skills are skipped).
5. Confirm with `git status --short skills/` and `git diff --stat -- skills/`. If nothing changed: remove the worktree and its branch (`git worktree remove …`, `git branch -D …`), report "no new or modified skills", and stop.
6. Privacy check: read every NEW skill in full, and for every UPDATED skill read its diff (`git diff -- skills/<name>`) plus any new files. If personal data appears (owner's full name, email address, employer or colleagues' names, home/OneDrive/C:\Users paths, resume or salary details, account IDs, secrets or tokens):
   - new skill: delete its folder and drop its entry from skills/index.json;
   - updated skill: `git checkout -- skills/<name>` (and `git clean -fd skills/<name>`) so the repo keeps the previous clean version.
   List each held-back skill and the reason in the report so the owner can add it to `exclude` in skills/sync.yaml. Do not edit sync.yaml yourself.
7. Run `uv run python -m unittest discover -s tests`. If tests fail, do not push; report the failure.
8. Commit only skills/ with message `feat: sync skills (added: <names>; updated: <names>)` (leave out an empty part), then a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Push the branch and open a PR to main with `gh pr create`, same title. The body lists: added skills; updated skills with a one-line summary of what changed in each (from the diff); orphaned skills; held-back skills and why. End the body with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Never merge the PR and never enable auto-merge.
9. Remove the worktree (keep the pushed branch). Report: PR link, added / updated (with change summary) / orphaned / held-back skills.
