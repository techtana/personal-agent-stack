---
type: llm
focus: trace
weight: 1
---

ux-review.md identifies the countdown timer as fake urgency because its deadline is computed from page-load time (Date.now()), so it restarts on every visit.
