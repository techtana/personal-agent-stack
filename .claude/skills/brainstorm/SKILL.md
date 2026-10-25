---
name: brainstorm
description: Architect-versus-critic debate on a design question, synthesised into an ADR under docs/decisions/ for human approval.
argument-hint: "<design question>"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Write, Agent
---

Run an adversarial brainstorm on: $ARGUMENTS

1. **Architect** (use the `app-dev` subagent): propose 2-3 approaches with trade-offs, constraints of this repo
   (read AGENTS.md and memory/state.md first), and a recommendation.
2. **Critic** (use the `code-review` subagent, fresh context, adversarial framing): attack each approach - failure modes,
   hidden costs, what breaks at 10x, what the architect ignored.
3. **Architect reply**: address each counterpoint or concede it.
4. **Synthesis** (you): write `docs/decisions/YYYY-MM-DD-<slug>.md` as an ADR (Title, Status: proposed, Context,
   Options considered with counterpoints, Decision, Consequences). Keep it under 120 lines.
5. Present the ADR and stop. The user approves by changing Status to accepted.
