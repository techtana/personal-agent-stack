# Design record

Every plan and decision for this project, in one place. Plans are history: an old plan is not rewritten to match
today's code; it gets a dated "Outcome" note instead.

- [DECISIONS.md](DECISIONS.md): the running decision log, newest first.
- [../decisions/](../decisions/README.md): architecture decision records (ADR format).
- [../ORCHESTRATOR-DESIGN.md](../ORCHESTRATOR-DESIGN.md): the current single-user design and measurements.

## Plans

| Date | Plan | Status |
|---|---|---|
| 2026-11-08 | [Read selected text aloud in every app](plans/2026-11-08-read-aloud.md) | built on branch `claude/read-aloud-highlighted-text-57ce4d`; tested with a test copy of the app and WAV output, not yet installed in the owner's voice typing app or heard through the speakers |
| 2026-11-08 | [Voice typing that learns the owner's voice](plans/2026-11-08-dictation-learning.md) | proposed; nothing built; P1-P2 need no owner decision, P3-P5 wait on L1-L4 |
| 2026-11-07 | [Voice typing in every app](plans/2026-11-07-voice-typing.md) | built on branch `claude/whisper-speech-to-text-extension-99ad1f`; tested with recorded speech, not yet with a live microphone |
| 2026-11-07 | [Refine selected text in every app](plans/2026-11-07-refine-selection.md) | built on branch `claude/ai-text-refinement-contextmenu-70d19f`; tested in test windows, a throwaway Word document and Edge, not yet in Logseq or Notion |
| 2026-11-01 | [Multimodal stack: vision, speech, images, video with audio, music, routing per message](plans/2026-11-01-multimodal-stack.md) | proposed; nothing built; next session starts from the [handoff](../HANDOFF-2026-11-01-multimodal.md) |
| 2026-11-01 | [`/ux-rules` UX rule catalog skill](plans/2026-11-01-ux-rules-skill.md) | done 2026-11-01 (PR #13); move into `skills/` and second eval round open |
| 2026-10-31 | [Skills library and `skills-sync`](plans/2026-10-31-skills-library.md) | done 2026-10-31 (PR #11); weekly scheduled task not created |
| 2026-10-29 | [Hard block on AI agents reading personal files](../plans/AGENT-FILE-ISOLATION.md) | proposed (PR #12); V-F1 checks run 2026-10-30; decisions D1-D4 open; nothing applied |
| 2026-10-26 | [Plan B: local-led, private first](../plans/PLAN-B-LOCAL-LED.md) | in progress: B-S0 spike and B2b supervision done (PR #7); B1 build core done 2026-10-28 (PR #8); B2-B6 not started |
| 2026-10-26 | [Shared components: privacy gate, build, identity, evals](../plans/SHARED-COMPONENTS.md) | proposed; checks V1-V8 and V11 done, V7/V9/V10 partly; S6 core done 2026-10-28 (PR #8); S1-S5, S7, S8 not built |
| 2026-10-26 | [Plan A: cloud-led on confidential VMs](../plans/PLAN-A-CLOUD-LED.md) | proposed; not started |
| 2026-10-26 | [Installation plan for both modes](../plans/INSTALL.md) | proposed; winget files generated, not yet applied on a clean account |
| 2026-10-26 | [Tray status window: design, usage, settings](plans/2026-10-26-tray-status-window.md) | done 2026-10-27 (PR #9); per-process view done 2026-10-28 (PR #8) |
| 2026-10-26 | [Google Cloud multi-user draft](../archive/GCP-DESIGN-DRAFT-2026-10-26.md) | dropped 2026-10-26 (replaced by Plan A) |
| 2026-10-25 | [Tray app that owns the services](plans/2026-10-25-tray-app.md) | done 2026-10-26 (PR #3) |
| 2026-10-24 | [Handoff: LiteLLM gateway, machine profiles, department agents](../HANDOFF-2026-10-24.md) | done 2026-10-26 (PR #2); Open WebUI first run, profile B and cloud tiers still unchecked |
| 2026-06-07 | Local-first router with cloud fallback (PR #1) | dropped 2026-10-25 (replaced by the LiteLLM gateway) |
| 2026-05-02 | [Deep-Architect design](../archive/DESIGN-2025.md) | dropped 2026-10-24 |
