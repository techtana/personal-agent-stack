# Stack state (mutable; machine facts, measurements, open items)

Updated: 2026-11-03 (tray Hugging Face / OpenClaw rows, OpenClaw gateway setup; open item 17). Before that, 2026-10-26 evening (B-S0 spike and B2b supervisor; Phoenix blocked by Smart App Control). Before that, 2026-10-25
late evening (uv tools start through their own Python; pid files carry start times). Earlier the
same day: default primary switched to qwen3.5:9b, and the MoE primary was benchmarked. First written 2026-10-24, when
the on-prem session executed docs/HANDOFF-2026-10-24.md.
Stable instructions live in AGENTS.md; durable lessons in memory/lessons.md; design in docs/ORCHESTRATOR-DESIGN.md.

## Machine: SEKAIHOME (profile: machines/SEKAIHOME.yaml, class moe-12gb-32ram, primary overridden to qwen3.5:9b)
- Windows 11 Pro, AMD Ryzen 5 5500 (6C/12T), 32 GB DDR4-2133 (2x16), RTX 3060 12 GB (driver 610.88, ~1.0 GB idle VRAM), C: ~36 GB free after installs, D: ~788 GB free.
- D: is a USB SSD (Micron Crucial X8); C: is an NVMe SSD (Kingston SNV3S). Model loads from D: are USB-bound.
  2026-11-01 `winsat`: D: read 41.6 MB/s (USB 2.0 link) until the owner turned the USB-C plug over, then 376 MB/s read /
  372 MB/s write; C: 2,762-2,990 MB/s read. The earlier 130-161 s cold loads of the 9B fit the 41 MB/s link. One plug
  orientation falls back to USB 2.0, so the cable or port has a bad contact. A second USB drive, E: (867 GB free),
  reads 42-43 MB/s (`stack.py disks`), cause not checked.
- Typical desktop load (Chrome, Claude apps, VS Code, Notion, Spotify, Logseq) leaves ~11-12 GB of the 32 GB RAM free before any model loads.
- Smart App Control is ON (VerifiedAndReputablePolicyState=1). Since 2026-10-25 19:34 it blocks `~/.local/bin/phoenix.exe`
  (WinError 4551; CodeIntegrity events 3033/3077). Each `~/.local/bin/*.exe` uv launcher embeds its script, so Windows
  judges every one as a new unsigned file. `stack.py up` no longer uses them: phoenix, litellm and open-webui start as
  `<uv tool dir>\<env>\Scripts\python.exe -P -c <console-script entry point>`. That python.exe is the same standard venv
  launcher in every environment and has not been blocked (no CodeIntegrity events since the switch).
- Installed 2026-10-24: Ollama 0.40.11 (native; models on D:\ollama\models), Claude Code CLI 2.1.302 (winget) alongside VS Code extension 2.1.296 and the desktop app, uv 0.12.17, Python 3.14 (system) / 3.12 and 3.11 (uv-managed), Node 24.
- Installed 2026-10-26 (B-S0): Microsoft OpenJDK 25.0.5 (winget MSI, `C:\Program Files\Microsoft\jdk-25.0.5.21-hotspot`, asked for UAC),
  Caddy 2.11.7 (winget portable, user scope), Keycloak 26.8.1 unpacked at D:\keycloak\keycloak-26.8.1 (SHA-1 checked; not a service;
  spike admin credentials in `.run/keycloak-spike.env` of the worktree that ran it). None run as services.
- uv tools: litellm[proxy] 1.106.3 (+ opentelemetry-sdk, opentelemetry-exporter-otlp), arize-phoenix 20.26, open-webui 0.12.3.
- NOT installed by choice: Docker Desktop / WSL2 (would reserve RAM the MoE experts need). Compose file kept as an untested optional path.
- Claude account: Max 5x subscription. No Anthropic API key on this machine; cloud tiers are off (all department tiers resolve to local-primary) until a key is added to .env and `stack.py build` is rerun.
- Ollama user env (registry, applied; the app was restarted 2026-10-25 via Explorer): FLASH_ATTENTION=1, KV_CACHE_TYPE=q8_0, NUM_PARALLEL=1, MAX_LOADED_MODELS=2, MAX_QUEUE=32, CONTEXT_LENGTH=32768, KEEP_ALIVE=30m, GPU_OVERHEAD=512 MiB, LOAD_TIMEOUT=15m, MODELS=D:\ollama\models.

## Local model roles on this machine (since 2026-10-25 evening)
- `local-primary` and `local-small` both serve qwen3.5:9b at num_ctx 32768 with Ollama's default load options, so all
  eight 9B deployments (primary, small, six `<dept>-local`) share one runner and never reload between tiers.
- The class default primary, qwen3.6:35b-a3b-coding, stays on disk (22 GB on D:) but no gateway alias uses it now.
  To bring it back as the default, delete the four override lines under `models:` in machines/SEKAIHOME.yaml and rebuild.
- `local-reviewer` still points at flint:40b-a2b, which is not pulled; no department tier routes to it.

## Services (native, `uv run scripts/stack.py up|down|status`)
| service | port | state 2026-10-25 late evening |
|---|---|---|
| Ollama | 11434 | up; tray app is a child of Explorer, so it survives Claude Code sessions |
| Phoenix | 6006 | down since 2026-10-26: Smart App Control blocks compiled modules in its tool env (pyarrow `_parquet`, sqlalchemy, pandas) |
| LiteLLM | 4000 | up via its tool Python; 17 model aliases; no OTel or callback errors |
| Orchestrator MCP | 8765/mcp | up (`uv run`); tools list/delegate/get_job/cancel_job/record_lesson; 401 without bearer |
| Open WebUI | 3000 | up (started by the tray); first run (admin user, model import, MCP server) not done |

Pid files in `.run/pids/` hold three lines: pid, executable, process start time. A pid counts as the service only while
a process with that pid and that start time exists, so a reused pid (for example one of the six long-lived `uv.exe`
MCP servers) is never stopped by mistake; verified by pointing the orchestrator pid file at one of them.

Since 2026-10-25 21:34 the services are owned by the tray app (`stack.py tray`, scripts/tray.py): a windowless
`.venv\Scripts\pythonw.exe` launched through Explorer, so neither it nor its services belong to a terminal or Claude Code
session. Its icon sits in the notification area's hidden icons; clicking it opens a status window with links to Open
WebUI, Phoenix and the LiteLLM admin UI. Start at login is ON since 2026-10-25 (`stack.py tray --remove-startup` or the tray's
checkbox removes the Startup-folder shortcut "Agent Stack.lnk"). Log: `.run/logs/tray.log`.
Since 2026-10-27 the window has three tabs: Overview (services, models loaded in Ollama), Usage (requests, tokens, latency,
tok/s and cost per gateway alias or served model from traces/litellm, tokens-per-day chart) and Settings (models, contexts,
tracing, Open WebUI, Ollama runtime; Apply patches machines/<HOST>.yaml in place, rebuilds and restarts what changed).
Cloud tiers stay read-only there on purpose (open item 4). Verified by screenshots and a headless apply; not yet run as the
live tray, which still runs the old code until it is restarted from the main checkout.

2026-11-01, tray UX fixes (branch claude/wonderful-hofstadter-9f02ef, merged to main in PR #15; the live tray runs
the new code only after a restart from the main checkout): a Start/Stop click changes its row on the Tk thread at once (measured 6-9 ms); each service has its own pending
state ("Starting... N s" in amber, Stop cancels a start) and a start waits only for its own service, so one service that
never answers no longer locks every control for 3 minutes; a service whose process is alive but not answering shows
as Starting, not Stopped; failures show under the row with Show log (Smart App Control or another refused start, missing
program, scheduled-task services, exit during start-up with the last log line, 3-minute timeout, exceptions); a
start-up failure under pythonw shows a message box and `stack.py tray` now waits up to 20 s for "[tray] ready" in
tray.log; the process sampler runs only while the Resources tab is on screen, backs off after failures, lists CPU as a
share of all logical processors and no longer lists the System Idle Process; the wheel over a Settings combobox
scrolls the form; every text colour passes 4.5:1 and every control shows a focus ring. `services.status()` checks
health in parallel: 2.1 s instead of 8.1 s here, because a refused localhost connection takes about 2 s on Windows.
Verified with a render harness that stubs the services (no real service started or stopped), `uv run --with pytest
pytest -q` (27 passed), and the ux-rules lint (no A11Y-01 candidates). Not verified: the launcher's success path through
Explorer (it would autostart services from a worktree) and the X11 wheel bindings.
At 03:40 that morning only Ollama answered its health check on this machine; the other services were down and were
left alone.

Before the tray, services started from a Claude Code tool shell stopped once (15:00 to 19:34, no reboot) and survived
once across a session restart.

## Verified on this machine
- 2026-10-26 late evening, private-only build (S6/B1) merged with the tray/metrics branch and deployed to the main
  checkout; `setup --no-pull`, tray restart: all five services UP (Phoenix included, receiving spans); 17 aliases, all
  `data_class: private`; unit tests 11/11. Full `smoke` 6/7 in 28 min (first chat 448 s, OpenAI tool call timed out)
  while the first requests queued behind warm-up; warm `smoke --dept docs` 8/8 in 72 s (chat 3.4 s); direct Ollama 80 tok/s.
- 2026-10-26, B-S0/B2b: Keycloak 26.8.1 `start-dev` 411 MB idle, ~515 MB after 300 logins (512 MB heap cap); Caddy
  served two internal-CA names over TLS; a `stack.py tasks` logon task restarted Phoenix's supervisor through its 2-minute
  watchdog trigger after a kill (Task Scheduler's restart on failure did not). Details in docs/plans/SHARED-COMPONENTS.md V7, V9, V10.
- 2026-10-25 late evening, services launched through the uv tool Pythons: phoenix, litellm and open-webui start
  healthy with no Smart App Control blocks; `stack.py smoke --dept docs` 8/8; Phoenix receives fresh LiteLLM spans;
  `down` stops a service's launcher and its child interpreter; restarting the orchestrator leaves the other `uv.exe`
  processes running; a stale pid file pointing at an unrelated `uv.exe` is detected and that process is left alone.
- 2026-10-25 evening, primary = qwen3.5:9b @32k: `stack.py smoke --dept docs` 8/8 passed (71 s warm; chat 2.8 s;
  OpenAI tool call and tool-result round trip; Anthropic `/v1/messages` with `thinking`, `text`, `tool_use`; router alias;
  embeddings; orchestrator MCP). First cold load of the 9B at 32k from D: took 2 min 10 s; one load, no reloads.
- 2026-10-25 afternoon, primary = qwen3.6:35b-a3b-coding: smoke 8/8 passed in 153 s (chat 28.6 s for a 141-token reply).
- 2026-10-24: gateway checks against qwen3.5:9b; JSONL traces in traces/litellm/; Phoenix spans;
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
| qwen3.5:9b (as primary, via gateway) | 32768 | 100% GPU | 130 s | not benched at 32k | - | 6.2 GB | ~17 GB |

- Without mmap (Ollama's Windows+CUDA default), the 35B load copied 12.65 GB of experts into anonymous memory with
  11.3 GB free and hit the 5-minute load timeout (HTTP 500). Fixed by `use_mmap: true` and `OLLAMA_LOAD_TIMEOUT=15m`.
- The 39-47 tok/s community figure for the 35B on an RTX 3060 is not reached here; DDR4-2133 and memory pressure
  from desktop apps are the likely limits. Not yet tried: `LLAMA_ARG_N_CPU_MOE` tuning, closing apps, faster RAM.

## Open items
1. If Smart App Control ever blocks the environments' python.exe as well, the remaining options are turning it off
   (a Windows security decision for you) or running the tools under the signed `uv` (`uv tool run`).
2. Start at login is on; after the next reboot or sign-in, confirm
   the tray and its services come up on their own.
8. Linux/macOS service management (tool Python launch, start-time pid matching) is written but untested on those systems.
3. Open WebUI first run at http://127.0.0.1:3000: create admin; Workspace > Models > Import each config/openwebui/*.json; Admin > Integrations > External Tool Servers > MCP (Streamable HTTP) http://127.0.0.1:8765/mcp with ORCHESTRATOR_BEARER from .env (2026-10-27: the connection was saved with WEBUI_SECRET_KEY, so every chat logged "Failed to connect to MCP server" and the orchestrator answered 401 invalid_token; fixed the same day by writing ORCHESTRATOR_BEARER into Open WebUI's `tool_server.connections` row, backup in `.run/open-webui/webui.db.bak-2026-10-27-mcp-key`; an MCP initialize and tools/list with the saved key returned the five tools).
4. Done 2026-10-26 (S6/B1 core): the build is private only. `policy/privacy.yaml` holds `external.enabled: false`; every
   deployment carries `data_class`/`location`; a tier, fallback, default or profile B alias naming a non-private
   deployment fails the build; `external.enabled: true` is refused until the gate (S1-S3) exists. Profile B sets
   `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` and denies WebFetch/WebSearch in `~/.claude-local/settings.json`.
   Still open from S6: guardrail entry, `database_url`, gate config, Open WebUI assets, compose output.
5. Run `scripts/claude-local.ps1` once to verify Claude Code profile B end to end (Read/Edit tool round trip through LiteLLM) on the 9B at 32k.
6. Revisit the 35B as primary after a RAM upgrade; the 9B fits entirely on the GPU and leaves ~17 GB of RAM available.
11. Elevated steps left from B-S0/B2b (admin terminal, main checkout): `winget configure --enable`; `uv run scripts/stack.py tasks
   install --trigger startup` once B2 lands; `kc.bat tools windows-service install` in S7. Phoenix is broken by Smart App Control
   and slated for removal (R); until then LiteLLM's otel callback has no collector.
9. Direction since 2026-10-26: private first (docs/plans/). Plan A runs on confidential VMs with a confidential model server
   and on-prem fallback; Plan B runs every tier locally. External APIs are off by default and only an explicit, consented,
   gated user choice. Not built yet. The earlier GCP draft is archived in docs/archive/GCP-DESIGN-DRAFT-2026-10-26.md.
   The LiteLLM admin UI (`/ui`) fails locally with "Not connected to DB!" because it needs Postgres; the tray link still points there.
10. Plan checks V1-V8 and V11 evaluated 2026-10-26 (results in docs/plans/SHARED-COMPONENTS.md section 7). V9 (`winget configure`),
   V10 (Task Scheduler) and the Keycloak runtime part of V7 change this machine and were not run; they belong to B-S0 and B2b.
12. Skills library (2026-10-31): `stack.py skills-sync` copies own skills into skills/. The weekly desktop scheduled task
   (prompt in skills/sync-task-prompt.md) is not created yet; it needs the sync merged to main first.
7. First `/retro` after a week of real traces; wire Open WebUI thumbs export when chat use starts.
13. Tray UX left after 2026-11-01: the "Restart Ollama?" stock OK/Cancel dialog (ux-rules CON-03), 8 pt chart axis
   labels (VIS-03), and selected rows in the Usage table and combobox lists marked only by the `select` background
   (1.21:1 light, 1.51:1 dark). Bare `uv run pytest` picks up a global pytest outside the project environment; use
   `uv run --with pytest pytest` until pytest is a dev dependency. Restart the tray from the main checkout after merging.
14. Multimodal stack (2026-11-01): plan in docs/design/plans/2026-11-01-multimodal-stack.md, handoff in
   docs/HANDOFF-2026-11-01-multimodal.md. Nothing installed or measured yet; spike M-S0 runs on this machine with the
   owner present. Session 1 (2026-11-01, planning only, worktree and scratchpad only) settled D-M1 to D-M8: open
   licences only, chain video, an open Foley model to find in S0e, DuckDuckGo per-chat search, four new departments.
   `stack.py status` that day: only Ollama up; LiteLLM, Open WebUI, Phoenix and the orchestrator down. Not run by the
   session (outside its folders): `stack.py doctor`, `ollama show qwen3.5:9b`; both are in T01 for the owner. Agent sessions work only on the drives and folders the owner selects at the start of each session;
   everything else is off-limits (plan C5, D-M6, task T08).
16. Installer additions (2026-11-01, branch claude/nervous-euclid-8357d0): steps **Check drive speed** (`stacklib/disks.py`,
   `stack.py disks`), **Set up the Hugging Face cache** (HF_HOME=<models drive>:\huggingface) and **Install OpenClaw**
   (Node.js here is 24.20.0, below openclaw's >=24.22.1, so the step will upgrade it to 26 LTS via winget with UAC).
   Verified: unit tests (53 passed), `stack.py disks` on C:, D: and E:, and a render of both installer pages. Not run:
   the HF and OpenClaw steps for real (they change user env vars, move the cache and upgrade Node.js).
17. Tray Hugging Face / OpenClaw status (2026-11-03, branch claude/agent-stack-tray-huggingface-d205d0): the Overview
   tab has a third card. The Hugging Face row shows HF_HOME, its size, and whether its drive is plugged in. The OpenClaw
   row shows where its models point: Gateway only, Not set up, Bypasses the gateway, or Uses an outside model. Its
   **Use gateway** button (also `stack.py openclaw`, and the installer's OpenClaw step) runs `stacklib/clients.setup_openclaw`.
   That onboards OpenClaw non-interactively if needed, then `openclaw config patch` adds provider `agent-stack`
   (127.0.0.1:4000/v1, the six departments plus local-primary), sets primary `agent-stack/app-dev` with no fallbacks,
   and removes off-gateway image/utility/pdf and per-agent models. The key goes to `~/.openclaw/.env`
   (LITELLM_MASTER_KEY; the json only names it). The window is now 860 px tall so the action bar fits.
   Verified: 22 unit tests (`uv run --with pytest pytest -q`: 96 passed). Fresh onboard and repair of a cloud config
   ran against a sandbox USERPROFILE. A real `openclaw agent --local` prompt went OpenClaw -> gateway ->
   qwen3.5:9b and back (PONG, 80 s cold). A render harness with stubbed services showed red -> Setting up... -> green.
   The owner's real `~/.openclaw` is set up (2026-11-04, owner approved): `stack.py openclaw --check` reports Gateway only,
   and a real `openclaw agent --local` prompt returned PONG through agent-stack/app-dev -> qwen3.5:9b (95 s cold). It was
   first written on 2026-11-03, before approval: a test whose mocks closed early ran the real setup. The original
   config is `~/.openclaw/openclaw.json.bak.3`. tests/test_clients.py now blocks the real setup module-wide.
   Restart the tray from the main checkout after merging.
15. Installer (2026-11-01, branch claude/interactive-installer-paths-77aabe): `install.cmd` / `stack.py install` asks for the models
   and Python tools folders, then runs setup in a detached worker (state in `.run/install/state.json`). That day drive D:
   (USB SSD) was not connected, so OLLAMA_MODELS=D:\ollama\models broke every pull. Verified with unit tests, a render
   harness and a stand-in worker; the real worker (registry, Ollama restart, pulls) has not run yet.
