# Stack state (mutable; machine facts, measurements, open items)

Updated: 2026-10-24 by the on-prem Claude Code session that executed docs/HANDOFF-2026-10-24.md.
Stable instructions live in AGENTS.md; durable lessons in memory/lessons.md; design in docs/ORCHESTRATOR-DESIGN.md.

## Machine: SEKAIHOME (profile: machines/SEKAIHOME.yaml, class moe-12gb-32ram)
- Windows 11 Pro, AMD Ryzen 5 5500 (6C/12T), 32 GB DDR4-2133 (2x16), RTX 3060 12 GB (driver 610.88, ~1.1 GB idle VRAM), C: ~36 GB free after installs, D: ~788 GB free.
- Installed 2026-10-24: Ollama 0.40.11 (native; models on D:\ollama\models), Claude Code CLI 2.1.302 (winget) alongside VS Code extension 2.1.296 and the desktop app, uv 0.12.17, Python 3.14 (system) / 3.12 and 3.11 (uv-managed), Node 24.
- uv tools: litellm[proxy] 1.106.3 (+ opentelemetry-sdk, opentelemetry-exporter-otlp), arize-phoenix 20.26, open-webui 0.12.3.
- NOT installed by choice: Docker Desktop / WSL2 (would reserve RAM the MoE experts need). Compose file kept as an untested optional path.
- Claude account: Max 5x subscription. No Anthropic API key on this machine; cloud tiers are off (all department tiers resolve to local-primary) until a key is added to .env and `stack.py build` is rerun.
- Ollama user env (registry): FLASH_ATTENTION=1, KV_CACHE_TYPE=q8_0, NUM_PARALLEL=1, MAX_LOADED_MODELS=2, MAX_QUEUE=32, CONTEXT_LENGTH=32768, KEEP_ALIVE=30m, GPU_OVERHEAD=512 MiB, MODELS=D:\ollama\models.
  The running Ollama instance still has CONTEXT_LENGTH=16384 from its first start; harmless (LiteLLM sends num_ctx per request); a restart (`stack.py setup` without --no-restart, or reboot) applies 32768.

## Services (native, `uv run scripts/stack.py up|down|status`)
| service | port | state 2026-10-24 |
|---|---|---|
| Ollama | 11434 | up |
| Phoenix | 6006 | up; receives LiteLLM OTLP spans (FastAPI spans visible in project `default`) |
| LiteLLM | 4000 | up; 17 model aliases (6 departments x router/local, local-fim/embed/small/primary/reviewer) |
| Orchestrator MCP | 8765/mcp | up; tools list/delegate/get_job/cancel_job/record_lesson; 401 without bearer |
| Open WebUI | 3000 | up; first-run (admin user, model import, MCP server) not done |

## Verified on this machine
- Gateway -> Ollama (qwen3.5:9b): chat, OpenAI tool call + tool-result round trip, Anthropic `/v1/messages` with `tool_use` block (Claude Code path), embeddings (768 dims).
- JSONL traces written to traces/litellm/ (requested alias, served model, call type, tokens, latency, failures); `why-routed` and `retro --reflect none` run.
- Claude Code hook script handles Stop/SubagentStop/PostToolUse payloads (escalation sentinel, pytest pass/fail detection).
- `claude-env` prints profile B; `claude-local.ps1` not yet run as a live session.
- promptfoo 0.125.0 validates the generated evals/docs config.

## Models pulled (D:\ollama\models)
- qwen2.5-coder:1.5b-base (986 MB, FIM), nomic-embed-text (274 MB), qwen3.5:9b (6.6 GB).
- qwen3.6:35b-a3b-coding (~22 GB): download in progress at the end of the session (ollama registry delivered ~3 MB/s after the first hour); resume with `ollama pull qwen3.6:35b-a3b-coding`.
- flint:40b-a2b (23 GB): not pulled; `uv run scripts/stack.py pull --all` when wanted.

## Benchmarks (fill with `uv run scripts/stack.py bench [--model m]`)
- qwen3.5:9b @16k: first load during a concurrent download took ~270 s; warm requests 1-5 s for short answers (tool-call turns ~1.0-1.5 s latency end to end). Decode tok/s not yet measured with `bench`.
- qwen3.6:35b-a3b-coding @32k: PENDING (model still downloading). Expected: experts in RAM, DDR4-2133 bound; if decode is poor try `LLAMA_ARG_N_CPU_MOE` in machines/SEKAIHOME.yaml:ollama_env.

## Open items
1. Finish `ollama pull qwen3.6:35b-a3b-coding`; run `stack.py bench` and `stack.py smoke`; record numbers here; if the MoE disappoints, set `models.primary: qwen3.5:9b` in the machine profile and rebuild.
2. Open WebUI first run at http://127.0.0.1:3000: create admin; Workspace > Models > Import each config/openwebui/*.json; Admin > Integrations > External Tool Servers > MCP (Streamable HTTP) http://127.0.0.1:8765/mcp with the bearer from .env.
3. Add ANTHROPIC_API_KEY to .env to enable cloud tiers (Max plans include monthly API credits; confirm in Console), then `stack.py build` and restart litellm.
4. Run `scripts/claude-local.ps1` once to verify Claude Code profile B end to end (Read/Edit tool round trip through LiteLLM).
5. First `/retro` after a week of real traces; wire Open WebUI thumbs export when chat use starts.
