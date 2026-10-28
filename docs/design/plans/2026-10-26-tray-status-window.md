# Tray status window: modern design, usage and settings

**Status:** done 2026-10-27 in [PR #9](https://github.com/techtana/personal-agent-stack/pull/9), except per-process
CPU/RAM/GPU (part 2), which is in open [PR #8](https://github.com/techtana/personal-agent-stack/pull/8).

## Goal

From [issue #4](https://github.com/techtana/personal-agent-stack/issues/4) (2026-10-26), the owner asked for:

1. A more modern tray window than default tkinter.
2. Current CPU, RAM and GPU use per process.
3. Average operation time (inference, input) per process and model, token counts for local and cloud models, cost
   so far for cloud, and a toggle for the accumulation period, all shown in the tray.
4. The tray icon, instead of the tkinter icon, on the window and the taskbar.

PR #9 added a fifth wish from the same session: change configuration from the tray without editing YAML.

## Approach (PR #9)

- Rebuild the status window as three tabs that follow Windows light/dark mode: **Overview**, **Usage**, **Settings**.
  The tray menu gains **Usage by model** and **Settings**.
- **Usage** reads the gateway's JSONL traces (`traces/litellm/*.jsonl`) through `scripts/stacklib/usage.py`, not
  Phoenix, because Smart App Control blocks Phoenix on SEKAIHOME. Period **Today** / **7 days** / **30 days**; group by
  gateway alias or served model; tiles, a sortable table and a tokens-per-day chart.
- **Settings** (`scripts/stacklib/settings.py`) edits a fixed list of keys in `machines/<HOST>.yaml`, keeps comments,
  re-parses before writing, runs the same generators as `stack.py build`, and restarts only what changed.
- Cloud tiers stay read-only: turning them on remains a `.env` decision (private first).

## Outcome (2026-10-27)

Parts 1, 3 (from traces) and the settings tab shipped. Part 2 shipped on `claude/orchestrator-redesign` (`28262a1`)
and waits in PR #8; that branch's Usage periods (1 h / 24 h / 7 d / 30 d / All) were replaced by PR #9's. Part 4 is
not recorded as done in either PR.
