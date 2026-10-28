# Design record

Every plan and decision for this project, in one place. Plans are history: an old plan is not rewritten to match
today's code; it gets a dated "Outcome" note instead.

- [DECISIONS.md](DECISIONS.md): the running decision log, newest first.
- [../decisions/](../decisions/README.md): architecture decision records (ADR format).
- [../ORCHESTRATOR-DESIGN.md](../ORCHESTRATOR-DESIGN.md): the current single-user design and measurements.

## Plans

| Date | Plan | Status |
|---|---|---|
| 2026-10-26 | [Plan B: local-led, private first](../plans/PLAN-B-LOCAL-LED.md) | in progress: B-S0 spike and B2b supervision done ([PR #7](https://github.com/techtana/personal-agent-stack/pull/7)); B1 build core in open [PR #8](https://github.com/techtana/personal-agent-stack/pull/8); B2-B6 not started |
| 2026-10-26 | [Shared components: privacy gate, build, identity, evals](../plans/SHARED-COMPONENTS.md) | proposed; checks V1-V8 and V11 done, V7/V9/V10 partly; S1-S8 not built (S6 in PR #8) |
| 2026-10-26 | [Plan A: cloud-led on confidential VMs](../plans/PLAN-A-CLOUD-LED.md) | proposed; not started |
| 2026-10-26 | [Installation plan for both modes](../plans/INSTALL.md) | proposed; winget files generated, not yet applied on a clean account |
| 2026-10-26 | [Tray status window: design, usage, settings](plans/2026-10-26-tray-status-window.md) | done 2026-10-27 (PR #9); per-process view in PR #8 |
| 2026-10-26 | [Google Cloud multi-user draft](../archive/GCP-DESIGN-DRAFT-2026-10-26.md) | dropped 2026-10-26 (replaced by Plan A) |
| 2026-10-25 | [Tray app that owns the services](plans/2026-10-25-tray-app.md) | done 2026-10-26 (PR #3) |
| 2026-10-24 | [Handoff: LiteLLM gateway, machine profiles, department agents](../HANDOFF-2026-10-24.md) | done 2026-10-26 ([PR #2](https://github.com/techtana/personal-agent-stack/pull/2)); Open WebUI first run, profile B and cloud tiers still unchecked |
| 2026-06-07 | Local-first router with cloud fallback ([PR #1](https://github.com/techtana/personal-agent-stack/pull/1)) | dropped 2026-10-25 (replaced by the LiteLLM gateway) |
| 2026-05-02 | [Deep-Architect design](../archive/DESIGN-2025.md) | dropped 2026-10-24 |
