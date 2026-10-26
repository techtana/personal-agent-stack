---
name: why-routed
description: Explain the gateway's recent routing decisions (which tier/model served each request and why) from the LiteLLM traces.
argument-hint: "[count]"
disable-model-invocation: true
allowed-tools: Bash(uv run scripts/stack.py why-routed*), Read
---

```
uv run scripts/stack.py why-routed --last ${ARGUMENTS:-10}
```

Summarise the output: for each request give department, requested model, served model, tier, cause/signals
(stall escalation, keyword, plan mode, context-window escalation), tokens and cost. Point out any request that went to
a cloud tier when the local tier would plausibly have sufficed, and vice versa, as candidates for the next `/retro`.
