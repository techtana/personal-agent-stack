---
name: no-closed-source-dependencies
description: The owner wants the agent stack app to have no dependency on closed-source software (Claude Desktop and similar)
metadata:
  type: feedback
---

The installed agent stack (tray, installer, services, features) must not depend on or integrate with closed-source
software such as Claude Desktop. Offer open-licence models and open-source runtimes only; check the licence of model
weights and of their training data before offering a download (no non-commercial, no-derivatives or custom restrictive
licences).

**Why:** On 2026-11-08 the owner saw the "Recordings in Claude Desktop" feature in the tray and said the app should not
have any dependency on non-open-source software "like claude, muse, etc." That feature was retired the same day (the
installer no longer offers it; it is remove-only while an old install exists).

**How to apply:** Do not add integrations that write into or rely on closed-source apps' configs or APIs. Prefer
open-source runtimes (ONNX Runtime, sherpa-onnx, Piper) and open-licence weights. The Claude Code developer tooling
around the repository (profile B, .claude/agents, the security audit skill) was left in place pending the owner's
answer; ask before removing it. Related: [[commit-push-pr-together]].
