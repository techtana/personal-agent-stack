---
name: harden
description: Hardening pass on the current change set before it ships - edge-case tests, dependency audit, docstrings, and a final lessons write-back.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
---

Harden the current change set (git diff against the base branch) in this order; stop and report after each step if something fails:

1. **Edge cases**: enumerate untested inputs for every changed public function (empty, max, unicode, concurrency, failure paths);
   add tests for the ones that matter. Use the `testing` subagent for bulk test generation.
2. **Dependencies and secrets**: run the project's audit (`npm audit --audit-level=high`, `uv pip audit` / `pip-audit`,
   `cargo audit`, `go vet` as applicable) and grep the diff for secrets. Remediate HIGH/CRITICAL or explain why not.
3. **Documentation**: add docstrings/JSDoc to exported symbols that lack them; update README/CHANGELOG if behaviour changed
   (use the `docs` subagent).
4. **Security spot-check**: hand the diff to the `security` subagent if it touches auth, input parsing, file or network I/O.
5. **Lessons**: append any durable lesson from this task to `memory/lessons.md` as a dated bullet.

Finish with a short checklist of what passed, what was skipped and why.
