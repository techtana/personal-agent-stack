---
name: commit-push-pr-together
description: When the owner asks to commit, also push and open the PR in the same turn; don't stop after the commit
metadata:
  type: feedback
---

When asked to commit finished work, do commit, push and open the PR in one go, in the same turn, without asking between the steps.

**Why:** On 2026-11-07 the owner was asked "Open a PR?" after a commit-only turn and said: in the future always do commit, push and PR in one step.

**How to apply:** Commit, then `git push -u origin HEAD`, then `gh pr create` against main (body ends with the Claude Code attribution line), then bind it with the ccd_pr tools. Merge only when the owner asks for it (they did on PR 29). The repo has no CI checks, and earlier PRs were merged with a merge commit (`gh pr merge --merge`).
