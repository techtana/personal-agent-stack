# Scheduled task: claude-security-audit

A Claude desktop scheduled task runs the audit weekly. It runs while the app is open; if the app is closed when the
task is due, it runs at the next launch.

- Task ID: `claude-security-audit`
- Schedule: weekly, Monday 09:30 local time (cron `30 9 * * 1`), after the `skills-sync` task at 09:00
- Prompt: everything below the line. It is self-contained, because each run starts without memory.

---

Weekly Claude security and confidentiality audit of this machine, using the claude-security-audit skill from the personal-agent-stack repository. Nobody is watching this run: ask no questions, list decisions for the owner in the final summary instead, and never write an email address, a person's name, the Windows user name or the GitHub account name anywhere (files, commits, PR text, summary).

Work in Git Bash. The main checkout is C:\Code\personal-agent-stack: do not edit, stash or switch branches in it.

1. `cd /c/Code/personal-agent-stack && git fetch -q origin main`. If `git show origin/main:.claude/skills/claude-security-audit/SKILL.md` fails, the skill is not merged yet: reply "claude-security-audit is not on main yet" and stop.
2. Refresh the audit worktree at origin/main. If `.claude/worktrees/security-audit` exists, run `git -C .claude/worktrees/security-audit checkout -q --detach origin/main`; otherwise `git worktree add -q --detach .claude/worktrees/security-audit origin/main`. From now on work inside it: `WT=/c/Code/personal-agent-stack/.claude/worktrees/security-audit`, `AUDIT="python $WT/.claude/skills/claude-security-audit/scripts/audit.py"`.
3. Read `$WT/.claude/skills/claude-security-audit/SKILL.md` and its reference files, then follow its "Scheduled run" section: `$AUDIT collect` (run from `$WT`), then the analysis, then `$AUDIT scrub --apply --no-local --repo $WT` and `$AUDIT scrub --apply --local-only`, then `$AUDIT add-analysis`, then `$AUDIT mark-reviewed`.
4. Pull request, only when scrub changed files in `$WT`:
   - If an open pull request from an `audit/identity-` branch exists (`gh pr list --state open --search "head:audit/identity-"`), don't add another; link the open one in the summary, and run `git -C $WT checkout -q -- .` to undo this run's edits.
   - Otherwise, `git config user.email` must end in `@users.noreply.github.com`; if it doesn't, don't commit, undo the edits as above, and say why in the summary. Then: `git -C $WT switch -c audit/identity-$(date +%F)`, run `uv run --with pytest python -m pytest -q` in `$WT` (if tests fail, don't push; report it), commit only the changed files with the message `fix: replace the owner's identity with placeholders`, a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, push, and open a pull request to main with `gh pr create`, using the same title. The body says which files changed and which kinds of identifier were replaced (counts only) and ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Never merge the PR and never enable auto-merge.
   - Afterwards: `git -C $WT checkout -q --detach origin/main`.
5. Final message, at most 12 lines: finding counts by severity; the three most important actions, each with the setting or command to apply; updates or advisories for installed versions; identity fixes (files and counts, plus the PR link); the report location from `$AUDIT where`.
