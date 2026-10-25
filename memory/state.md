# Stack state (mutable; machine facts, measurements, open items)

Updated: 2026-10-25 (benchmark and smoke test of the MoE primary). Previous update: 2026-10-24, when the
on-prem session executed docs/HANDOFF-2026-10-24.md.
Stable instructions live in AGENTS.md; durable lessons in memory/lessons.md; design in docs/ORCHESTRATOR-DESIGN.md.

## Machine: SEKAIHOME (profile: machines/SEKAIHOME.yaml, class moe-12gb-32ram)
- Windows 11 Pro, AMD Ryzen 5 5500 (6C/12T), 32 GB DDR4-2133 (2x16), RTX 3060 12 GB (driver 610.88, ~1.0 GB idle VRAM), C: ~36 GB free after installs, D: ~788 GB free.
- D: is a USB SSD (Micron Crucial X8); C: is an NVMe SSD (Kingston SNV3S). Model loads from D: are USB-bound.
- Typical desktop load (Chrome, Claude apps, VS Code, Notion, Spotify, Logseq) leaves ~11-12 GB of the 32 GB RAM free before any model loads.
- Installed 2026-10-24: Ollama 0.40.11 (native; models on D:\ollama\models), Claude Code CLI 2.1.302 (winget) alongside VS Code extension 2.1.296 and the desktop app, uv 0.12.17, Python 3.14 (system) / 3.12 and 3.11 (uv-managed), Node 24.
- uv tools: litellm[proxy] 1.106.3 (+ opentelemetry-sdk, opentelemetry-exporter-otlp), arize-phoenix 20.26, open-webui 0.12.3.
- NOT installed by choice: Docker Desktop / WSL2 (would reserve RAM the MoE experts need). Compose file kept as an untested optional path.
- Claude account: Max 5x subscription. No Anthropic API key on this machine; cloud tiers are off (all department tiers resolve to local-primary) until a key is added to .env and `stack.py build` is rerun.
- Ollama user env (registry, applied; the app was restarted 2026-10-25 via Explorer): FLASH_ATTENTION=1, KV_CACHE_TYPE=q8_0, NUM_PARALLEL=1, MAX_LOADED_MODELS=2, MAX_QUEUE=32, CONTEXT_LENGTH=32768, KEEP_ALIVE=30m, GPU_OVERHEAD=512 MiB, LOAD_TIMEOUT=15m, MODELS=D:\ollama\models.
- Gateway sends `use_mmap: true` for the primary and reviewer (hardware class `primary_options`); confirmed forwarded by LiteLLM (no reload of the primary during the smoke test).

## Services (native, `uv run scripts/stack.py up|down|status`)
| service | port | state 2026-10-25 |
|---|---|---|
| Ollama | 11434 | up; tray app now a child of Explorer, not of a tool shell |
| Phoenix | 6006 | up; receives LiteLLM OTLP spans |
| LiteLLM | 4000 | up; 17 model aliases (6 departments x router/local, local-fim/embed/small/primary/reviewer) |
| Orchestrator MCP | 8765/mcp | up; tools list/delegate/get_job/cancel_job/record_lesson; 401 without bearer |
| Open WebUI | 3000 | down (not needed for the smoke test); first run (admin user, model import, MCP server) not done |

The services started on 2026-10-24 were killed when that session's tool shell exited. `stack.py up` now
launches them outside the launching shell's job (CREATE_BREAKAWAY_FROM_JOB); survival across a session end is
not yet observed.

## Verified on this machine
- 2026-10-25 smoke test, `stack.py smoke --dept docs`, primary = qwen3.6:35b-a3b-coding: 8/8 passed in 153 s
  (model list; chat 28.6 s for a 141-token reply on the first gateway request; OpenAI tool call and tool-result
  round trip; Anthropic `/v1/messages` with `thinking`, `text`, `tool_use` blocks; department router alias;
  embeddings 768 dims; orchestrator MCP tools and 6 departments).
- 2026-10-24: same gateway checks against qwen3.5:9b; JSONL traces in traces/litellm/; Phoenix spans;
  hook script parses Stop/SubagentStop/PostToolUse; `why-routed` and `retro --reflect none` run; promptfoo validates evals/docs.
- `claude-env` prints profile B; `claude-local.ps1` not yet run as a live session.

## Models pulled (D:\ollama\models)
- qwen2.5-coder:1.5b-base (986 MB, FIM), nomic-embed-text (274 MB), qwen3.5:9b (6.6 GB), qwen3.6:35b-a3b-coding (22 GB, Q4_K_M, 35.5B total, 256 experts / 8 active).
- flint:40b-a2b (23 GB): not pulled; `uv run scripts/stack.py pull --all` when wanted.

## Benchmarks (2026-10-25, `uv run scripts/stack.py bench`, 256 generated tokens, 54-token prompt)
| model | ctx | placement | cold load | warm decode tok/s | warm prefill tok/s | VRAM (model) | RAM available while loaded |
|---|---|---|---|---|---|---|---|
| qwen3.6:35b-a3b-coding, use_mmap | 32768 | 42/42 layers on GPU; expert tensors of 28 layers in mapped RAM (~12.7 GB); `ollama ps` 98% GPU | 331 s, then first reply at 2.6 tok/s while pages fault in | ~25 (five warm runs: 21.5, 33.0, 22.4, 25.1, 24.5) | 183-462 (noisy on a short prompt) | 9.3 GB (11.4 GB total on card) | ~1 GB (Windows paging ~110 pages/s) |
| qwen3.5:9b | 16384 | 100% GPU | 161 s | 51-52 (four runs) | 865-927 | 5.9 GB (8.0 GB total on card) | ~17.9 GB |

- Without mmap (Ollama's Windows+CUDA default), the 35B load copied 12.65 GB of experts into anonymous memory with
  11.3 GB free and hit the 5-minute load timeout (HTTP 500). Fixed by `use_mmap: true` and `OLLAMA_LOAD_TIMEOUT=15m`.
- The 39-47 tok/s community figure for this model on an RTX 3060 is not reached here; DDR4-2133 and memory pressure
  from desktop apps are the likely limits. Not yet tried: `LLAMA_ARG_N_CPU_MOE` tuning, closing apps, faster RAM.

## Open items
1. Decide the default primary. The 35B MoE runs at ~25 tok/s but leaves ~1 GB of RAM available with the usual apps
   open; the 9B runs at ~52 tok/s with ~18 GB available. To make the 9B the default and keep the 35B on demand, set
   `models.primary: qwen3.5:9b` in machines/SEKAIHOME.yaml and rebuild. Upgrading RAM to 64 GB removes the trade-off.
2. Open WebUI first run at http://127.0.0.1:3000: create admin; Workspace > Models > Import each config/openwebui/*.json; Admin > Integrations > External Tool Servers > MCP (Streamable HTTP) http://127.0.0.1:8765/mcp with the bearer from .env.
3. Add ANTHROPIC_API_KEY to .env to enable cloud tiers (Max plans include monthly API credits; confirm in Console), then `stack.py build` and restart litellm.
4. Run `scripts/claude-local.ps1` once to verify Claude Code profile B end to end (Read/Edit tool round trip through LiteLLM). With the 35B primary, size `CLAUDE_CODE_MAX_CONTEXT_TOKENS` to 32768 (already generated).
5. Confirm the services survive the end of the Claude Code session that started them (`stack.py status` in a new session).
6. First `/retro` after a week of real traces; wire Open WebUI thumbs export when chat use starts.
