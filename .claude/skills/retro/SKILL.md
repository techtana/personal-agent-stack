---
name: retro
description: Run the stack retrospective over recent traces and review its proposed deltas to prompts, routing or lessons. Never applies changes without approval.
argument-hint: "[days]"
disable-model-invocation: true
allowed-tools: Bash(uv run scripts/stack.py retro*), Read, Grep, Glob
---

Run the retrospective for the last `$ARGUMENTS` days (default 7):

```
uv run scripts/stack.py retro --days ${ARGUMENTS:-7}
```

Then:
1. Read the report it names under `retro/reports/`.
2. Summarise per department: requests, local vs cloud share, escalations, stalls, test pass rate, cost.
3. For each proposed delta (at most 3), show the exact file and bullet-level change as a diff and the evidence (trace ids).
4. Ask which deltas to apply. Apply only approved ones by editing `agents/<id>.yaml`, `memory/lessons.md` or
   `machines/<host>.yaml`, then run `uv run scripts/stack.py build` and the promptfoo gate for touched departments:
   `npx promptfoo@0.125.0 eval -c evals/<id>/promptfooconfig.yaml`.
5. Never auto-merge. Leave the changes for the user to commit.
