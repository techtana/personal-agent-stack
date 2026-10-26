# Lessons (append-only, dated; ACE-style deltas, never rewrite history)

- [2026-10-24] Do not rebuild the agent harness: Claude Code / OpenCode / Cline already ship loops, tools, subagents, hooks, MCP, AGENTS.md.
- [2026-10-24] A hand-rolled OpenAI-compatible proxy breaks tool-using clients; use LiteLLM (`ollama_chat/` for tools, `/v1/messages` for Claude Code).
- [2026-10-24] Run Ollama natively on Windows, not in Docker. One large local model resident at a time on 12 GB.
- [2026-10-24] Haiku 5.5 at $0.10/$0.50 per MTok changes the local-vs-cloud break-even; local pays off for privacy, autocomplete and the MoE tier.
- [2026-10-24] Since 2026-10-21 `temperature`/`top_p`/`top_k` return HTTP 400 on every Claude model; `output_config.effort` is the cost lever. Set temperature only on local deployments.
- [2026-10-24] Keep one source of truth for department prompts (`agents/*.yaml`) and generate per-tool files; duplicated prompts drifted within one session.
- [2026-10-24] Self-development is a human-gated nightly PR loop with an eval gate, never auto-merge.
- [2026-10-24] Ollama >= 0.30 runs GGUF through upstream llama-server with `LLAMA_ARG_FIT=on`, which is MoE-aware (experts to CPU, attention on GPU). A separate llama-server install is unnecessary; `LLAMA_ARG_N_CPU_MOE=N` passes through as a manual override.
- [2026-10-24] The handoff assumed Ollama, Docker and Open WebUI were installed; none were. Always run `stack.py doctor` before trusting a handoff's environment claims.
- [2026-10-24] Claude Code reads AGENTS.md natively only when no CLAUDE.md exists; a CLAUDE.md that `@AGENTS.md`-imports it keeps both tools and the memory files in context.
- [2026-10-24] In `.mcp.json`, env var names that look like credentials (`*_API_KEY`, `*_TOKEN`) read as empty; name the orchestrator bearer `ORCHESTRATOR_BEARER`.
- [2026-10-25] Ollama 0.40 disables mmap by default on Windows+CUDA ("windows_cuda" in server/sched.go), copying CPU-side MoE experts into anonymous RAM. With desktop apps holding ~20 GB, the 35B load paged and hit the 5-minute `OLLAMA_LOAD_TIMEOUT` (HTTP 500). Send `use_mmap: true` per request (LiteLLM forwards it into Ollama `options`) and raise the timeout.
- [2026-10-25] On this box the MoE primary decodes at ~25 tok/s versus ~52 for the dense 9B, and leaves ~1 GB of RAM available instead of ~18 GB. Benchmark both before choosing; RAM pressure, not VRAM, is the binding constraint.
- [2026-10-25] Processes started from an agent's tool shell die when that session ends (job object). Launch services with CREATE_BREAKAWAY_FROM_JOB and the Ollama tray app through explorer.exe.
- [2026-10-25] Windows reuses pids: never kill or trust a pid file without checking the process image name.
- [2026-10-25] Correction to the CREATE_BREAKAWAY_FROM_JOB bullet above: services started that way from a Claude Code tool shell still stopped when the session restarted. Persistent services need a launcher outside the session (Task Scheduler, a logon item, or the owner's own terminal).
- [2026-10-25] Smart App Control can block unsigned uv tool launchers (`~/.local/bin/*.exe`) file by file: phoenix.exe was blocked (WinError 4551) while litellm.exe still ran. Service start must warn and continue, never abort the batch.
- [2026-10-25] When two gateway tiers share one Ollama model, give them the same num_ctx and load options; any difference makes Ollama reload the runner on every switch between tiers.
