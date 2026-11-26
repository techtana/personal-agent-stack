# Default primary for a 12 GB GPU with 32 GB of RAM: the dense 9B, the 35B MoE opt-in

Status: accepted (2026-11-26)

## Context

The owner checked the reference machine's spec in Task Manager: 31.9 GB of RAM with about 15 GB in use at idle,
an RTX 3060 with 12.0 GB of dedicated VRAM (15.9 GB "shared GPU memory", which is system RAM that Windows lends the
card and Ollama does not use as VRAM), and C: on an NVMe SSD. The detection (`nvidia-smi` for the card, total
physical memory for RAM) puts this machine in `moe-12gb-32ram`, as before: the GPU and RAM are recorded correctly.

That class's default primary was `qwen3.6:35b-a3b-coding`, from the 2026-10-24 handoff ("viable at >= 32 GB").
The measurements since then disagree with making it the default:

- Bench (2026-10-25, `memory/state.md` Benchmarks): the 35B decodes at ~25 tok/s with ~12.7 GB of experts in
  memory-mapped RAM, 9.3 GB of VRAM, a 331 s cold load and ~1 GB of RAM left; the 9B decodes at 51-52 tok/s wholly on
  the GPU (5.7 GB at 32k) and leaves ~17 GB of RAM.
- With ~15 GB in use at idle, ~17 GB is free before a model loads. The 35B's experts and runner take ~13-14 GB of it,
  leaving 3-4 GB for the desktop's growth, so paging returns as soon as the browser grows.
- On the GPU the 35B needs ~11.4 GB, so it does not fit beside voice typing's Whisper or images on a 12 GB card.
- The system check (`stacklib/syscheck.py`, open item 42) already recommends `qwen3.5:9b` at 32k for this exact
  hardware and rates the 35B "ok", and the reference machine's own profile overrides the primary to the 9B. But a
  profile written fresh (2026-11-08, open item 30) took the class default and pulled the 35B.

Claude Code billing was checked at the same time, against the plan that Claude Code stays on the Max subscription:

- Profile A (plain `claude`, the default): no `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` or `ANTHROPIC_API_KEY` is
  set. `.claude/settings.json` sets only `CLAUDE_CODE_GATEWAY_HINT_HEADERS`, which matters only behind a custom base
  URL. PR #65 puts `LITELLM_CLAUDE_KEY` and `ORCHESTRATOR_CLAUDE_BEARER` in `.claude/settings.local.json`'s `env`;
  Claude Code does not read either as a credential (`.mcp.json` reads the bearer for the agent tools). Billing stays
  on the subscription login.
- Profile B (`scripts/claude-local.ps1|sh`, opt-in): `ANTHROPIC_BASE_URL` is the local LiteLLM gateway,
  `ANTHROPIC_AUTH_TOKEN` is Claude's own gateway key `LITELLM_CLAUDE_KEY` (not an Anthropic API key, not the master
  key), `ANTHROPIC_API_KEY` is empty, in its own `CLAUDE_CONFIG_DIR`. That process leaves the subscription, but the
  gateway serves private local aliases only (`policy/privacy.yaml` external off; no Anthropic deployment in the
  generated config), so it spends local tokens and no Anthropic money.

This matches the plan, so it needs no change.

## Options considered

1. Keep the 35B as the class default and rely on the system check and per-machine overrides. A profile written
   without the installer's page (`doctor --write-profile`, a fresh profile through setup) still pulls 23 GB and gets
   the slower, paging model.
2. Make the 9B the class default and keep the 35B as an opt-in. Fresh profiles match the measured best choice and
   the system check; the 35B stays one choice away.
3. Add a new class for this hardware. Renaming or splitting `moe-12gb-32ram` would orphan the class name already
   recorded in existing local profiles, for no gain over option 2.

## Decision

Option 2. In `machines/_defaults.yaml`, `moe-12gb-32ram` now has `primary: qwen3.5:9b`, `primary_num_ctx: 32768`,
`small_num_ctx: 32768` (was 16384, so primary and small share one runner instead of reloading between tiers) and
`primary_options: {}` (memory-mapped weights only for an MoE; the reviewer `flint:40b-a2b` keeps `use_mmap: true`).
Unchanged: `max_loaded_models: 2`, the Ollama environment (flash attention, q8_0 KV cache, one parallel request,
512 MiB GPU overhead, 15 min load timeout), and both Claude Code profiles.

## Consequences

- A fresh profile on this hardware resolves to what the reference machine already runs and what the committed
  gateway config holds (9B at 32k for local-primary and local-small), so its existing four-line override becomes
  redundant but harmless.
- The 35B stays usable: choose it in the installer (which sets memory-mapped experts itself) or in the tray's
  Settings with "Memory-map primary weights" on. Worth trying again when RAM use at idle falls or RAM is added.
- Not verified on the machine: `stack.py build` and `bench` were not run from this change (the profile is local to
  the machine). Run `uv run scripts/stack.py profile` there to confirm the resolved values.
