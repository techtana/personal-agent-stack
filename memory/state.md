# Stack state (mutable; machine facts, measurements, open items)

Updated: 2026-11-08 (the installer makes an app apart from the repository; open item 32). Before that, the same day (the installer asks which features to install, with their load on this PC, and the tray's Features card; open item 30). Before that, 2026-11-08 (voice typing's cleanup prompt is a setting; open item 23). Before that, 2026-11-07 night (PAS-<Name> process names; open item 29). Before that, the same night (privacy cleanup, machine profiles local; open item 28). Before that, the same night (refine selected text in every app; open item 27). Before that, the same night (Open WebUI's microphone on voice typing's Whisper; open item 26). Before that, 2026-11-07 late evening (the Usage tab counts every model the stack runs; open item 25). Before that, 2026-11-07 (Claude security audit skill and standing identity rule; open item 24). Before that, the same day (voice typing in every app; open item 23). Before that, 2026-11-03 (tray Hugging Face / OpenClaw rows, OpenClaw gateway setup; open item 17). Before that, 2026-10-26 evening (B-S0 spike and B2b supervisor; Phoenix blocked by Smart App Control). Before that, 2026-10-25
late evening (uv tools start through their own Python; pid files carry start times). Earlier the
same day: default primary switched to qwen3.5:9b, and the MoE primary was benchmarked. First written 2026-10-24, when
the on-prem session executed docs/HANDOFF-2026-10-24.md.
Stable instructions live in AGENTS.md; durable lessons in memory/lessons.md; design in docs/ORCHESTRATOR-DESIGN.md.

## Reference machine (local profile machines/<HOST>.yaml, class moe-12gb-32ram, primary overridden to qwen3.5:9b)
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

## Media: images (2026-11-04, branch claude/hf-not-working-0777b4)
- Owner chose `D:\media` (ComfyUI, models, inputs, outputs, uv cache) and `D:\huggingface` (HF_HOME) as the only
  folders for media tools and agent sessions; both are in `agent_access.allowed_roots` of machines/<HOST>.yaml.
- ComfyUI 0.44.0 (commit 56f179f6) in `D:\media\comfyui`, venv from python.org Python 3.14.7, torch 2.14.1+cu130
  (CUDA available on the RTX 3060). First `import torch` took 47 s (Smart App Control scanning the new DLLs).
- Smart App Control refused PyAV 19.0.2 (`av\audio\frame.pyd`, CodeIntegrity 3033) and 16.0.1; 17.0.0 runs. Pinned.
  It also refused SQLAlchemy's Cython speed-up (`_collections_cy.cp314`); SQLAlchemy falls back to pure Python.
- Z-Image-Turbo int8 (6.2 GB) + Qwen3-4B fp8 text encoder (5.6 GB) + VAE (0.3 GB), all Apache-2.0, in
  `D:\media\comfyui\models`. 1024 x 1024, 8 steps, no chat model loaded: 32.1 s cold (load from D:), 11.0 s warm,
  peak 11.6 GB VRAM on the card. Open WebUI's own ComfyUI code with the saved settings: 10.2 s. `smoke --media-only`
  (512 px, 4 steps, right after a GPU switch to chat): 25.1 s.
- GPU mode: **Chat** (`POST /free` to ComfyUI) took the card from 8.6 GB to 0.8 GB used.
- Open WebUI image settings written into `.run/open-webui/webui.db` of the main checkout (backup
  `webui.db.bak-20261104-015437-media`); Open WebUI reads its config rows per request, so no restart was needed.
- Not verified: the image button clicked in the browser (the built-in browser could not open 127.0.0.1:3000), an image
  with the 9B loaded under `--lowvram`, the installer's media step run end to end (the pieces ran by hand), the tray's
  new GPU card and ComfyUI setting in the live tray (rendered from the worktree only).
- At 01:49:14 on 2026-11-04 the tray stopped its services and exited and Ollama shut down at the same moment, from
  outside this session (both logs). ComfyUI was then running only from the session's shell.

## Local model roles on this machine (since 2026-10-25 evening)
- `local-primary` and `local-small` both serve qwen3.5:9b at num_ctx 32768 with Ollama's default load options, so all
  eight 9B deployments (primary, small, six `<dept>-local`) share one runner and never reload between tiers.
- The class default primary, qwen3.6:35b-a3b-coding, stays on disk (22 GB on D:) but no gateway alias uses it now.
  To bring it back as the default, delete the four override lines under `models:` in machines/<HOST>.yaml and rebuild.
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
3. Open WebUI first run at http://127.0.0.1:3000: create admin; Workspace > Models > Import each config/openwebui/*.json; Admin > Integrations > External Tool Servers > MCP (Streamable HTTP) http://127.0.0.1:8765/mcp with ORCHESTRATOR_BEARER from .env (2026-10-27: the connection was saved with WEBUI_SECRET_KEY, so every chat logged "Failed to connect to MCP server" and the orchestrator answered 401 invalid_token; fixed the same day by writing ORCHESTRATOR_BEARER into Open WebUI's `tool_server.connections` row, backup in `.run/open-webui/webui.db.bak-2026-10-27-mcp-key`; an MCP initialize and tools/list with the saved key returned the five tools). 2026-11-04: the saved connection's ID is
   `personal-agent-stack`; the generated department models now carry `meta.toolIds: ["server:mcp:personal-agent-stack"]`
   and `params.function_calling: native`, so the orchestrator tools are on in new chats with them. Open WebUI had no
   workspace models that day (none imported yet); the import and a chat with the tools on are not verified.
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
17. First-query load time (2026-11-04, branch claude/first-query-load-time-0363f4): the gateway no longer sends
   keep_alive for chat models (local-small's 30m used to cut local-primary's -1 short on the shared 9B runner), so
   OLLAMA_KEEP_ALIVE decides for all of them; its default is now 4h. The tray (at autostart, waiting up to 5 min for
   Ollama) and `stack.py up` (unless --no-warm) load the primary with its gateway num_ctx and options. Verified: unit
   tests 79 passed; live cold warm-up 23.3 s from D:, the next 32k request loaded in 3 ms and answered in 0.23 s. Not done:
   this machine's registry still has OLLAMA_KEEP_ALIVE=30m (set 4h in the tray's Settings, which restarts Ollama, or
   rerun setup), and the live tray runs the new code only after a restart from the main checkout.
18. Tray Hugging Face / OpenClaw status (2026-11-03, branch claude/agent-stack-tray-huggingface-d205d0): the Overview
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
19. Multimodal, after images (2026-11-04): next packages are vision and new departments (M1), speech with Kokoro
   (M2), the Auto router (M3), style transfer (T43), video with audio and music (M5a), web search (M6). Each is one PR.
20. Model label (2026-11-04, branch claude/expose-model-info-978e1d): every chat reply through the gateway ends with
   `**Used:** qwen3.5:9b (Local) via <alias>` (router aliases keep their **Route:** line), and after Open WebUI made an
   image, `**Image:** Z-Image-Turbo int8 (ComfyUI, 1024x1024, 8 steps)`. Open WebUI calls ComfyUI directly, so the gateway
   spots the image by the `<context>The requested image has been ...created` system text Open WebUI 0.12 adds to the
   follow-up chat request; the label comes from the profile, not from Open WebUI's admin settings. JSON-mode requests,
   tool calls and FIM completions get no footer. Switch: `observability.model_label` (tray: Show model in replies).
   Verified: unit tests 134 passed; a second gateway on port 4010 with this code answered local-primary, app-dev,
   an image-context request, JSON mode and a streamed reply as expected. Not verified: the image button in the browser.
   The live gateway shows the new label only after the tray restarts from the main checkout.
21. Tray Usage breakdown (2026-11-04, branch claude/3060-performance-34932a): every request still counts, and each
   row expands into one row per client (Open WebUI, Claude Code, OpenClaw, Orchestrator, Stack scripts, curl, from
   the User-Agent); "Group by Client" flips it. Output tok/s became Decode tok/s (Ollama's own eval time, timed requests
   only) and Overall tok/s (all output over all wall-clock time). A line under the table splits the selected row's time
   into load + prompt + generate + gateway/queue for timed requests, and the average wall clock of untimed ones.
   On this box that day: decode 50-52 tok/s on every timed request; Open WebUI's untimed calls (~7k-token prompts,
   ~230-token replies, likely title/tag tasks) waited behind chat replies (NUM_PARALLEL=1), so overall was 33 tok/s.
   Traces now record `stream`, to show whether the untimed requests are the streamed ones (gateway restart needed).
   Verified: unit tests, a render of the Usage tab from the worktree with stubbed services and real traces.
22. Recordings (2026-11-05, branch claude/whisper-local-cowork-integration-820acc): faster-whisper 1.2.1 (ctranslate2
   4.8.5, PyAV 17.0.0, cuBLAS 12.9 / cuDNN 9.28 wheels) in `D:\media\whisper\.venv` from python.org 3.14.7;
   large-v3-turbo in `D:\huggingface`. `stack.py whisper install` registered the `local-whisper` MCP server in
   `%APPDATA%\Claude\claude_desktop_config.json` (backup `.bak-20261105-233938`; unity-mcp kept). Verified over stdio
   with that exact entry: four tools, GPU transcription (12 s clip 0.7 s warm, 125 s in 3.5 s, ~1.1 GB VRAM), cache,
   job polling, refusal outside allowed_roots; unit tests 149 passed. Not verified: Claude Desktop restarted and the
   tools used from a Cowork task, a real phone/meeting recording (only eSpeak WAVs), m4a/mp4 input, Thai.
23. Voice typing (2026-11-07, branch claude/whisper-speech-to-text-extension-99ad1f): service `dictation`
   (scripts/stacklib/dictation, port 8790 for health and control), a floating mic button and Ctrl+Alt+D type speech
   into the focused app. faster-whisper 1.2.1 + CTranslate2 4.8.5 in `D:\media\dictation\.venv` (python.org 3.14;
   every compiled module loaded under Smart App Control); large-v3-turbo from `D:\huggingface` (already cached) on the
   GPU through Ollama's `lib\ollama\cuda_v12\cublas64_12.dll`. Load 5-8 s; 0.3 s for 3.5 s of speech, 0.6 s for
   15 s; +1.2 GB VRAM (9.2 of 12 GB with the 9B). CPU turbo: 9.7 s for 15 s, so `cpu_model: small`. Cleanup via
   `local-small` with `think: false` and JSON mode: 0.55-1.2 s. `services.dictation: native` is set in
   machines/<HOST>.yaml. Verified: 39 new unit tests (180 passed in total); `stack.py dictate transcribe` on Windows
   TTS recordings (phrases, silence stop, Thursday->Friday correction); the running app with a replayed recording
   pasting into a Tk test window (clipboard restored) and typing live phrases. Ctrl+Alt+Space is taken here (Claude
   desktop quick entry), hence Ctrl+Alt+D. Not verified: a live microphone and hand-pressed hotkey, the bubble's look
   (screen capture refused), pasting into Logseq/Word/Notion, languages other than English, the tray's new row and
   settings in the live tray. Later on 2026-11-07: the language choice covers all 100 Whisper codes through a type-to-search
   picker (button menu and tray Settings); its filtering and keyboard choice were checked in an invisible window, its
   look and the tray button were not.
   Also verified: cancel, a second instance, hold-to-talk with injected Ctrl+Alt+D (live text typed at release). A
   code review's eight findings and its clipboard-owner risk were fixed (owner window per clipboard operation; restore
   after 1 s). At the end of the session the app was left running from the worktree (pid file in the worktree's .run).
   2026-11-07 late evening (branch claude/voice-typing-cleanup-config-d44300): the cleanup prompt is a setting,
   `dictation.cleanup_prompt` (`''` = the built-in text, which is unchanged), edited in the tray under Settings > Voice
   typing > Show advanced. Apply hands it to the running app (`POST /reload`, also `stack.py dictate reload`) instead
   of restarting it. The concise rule, the JSON reply format and the reply checks stay in code. yamledit now writes
   multi-line text as a literal block and replaces a multi-line value whole. Verified: unit tests (`uv run --with
   pytest pytest -q`); a render harness of the Settings tab (dark and light, closed and open, edit, save, Restore
   default, Ctrl+Z, Tab) against a temp copy of the machine file; the app's reload in the voice typing venv; both
   prompts on qwen3.5:9b through Ollama directly (LiteLLM was down): a custom spelling-and-digits rule held 6/6 and the
   self-correction 6/6. Not verified: the live tray and app (they run the new code only after a restart from the main
   checkout), and a dictation through LiteLLM with a custom prompt. At 23:00 only Ollama was up (the 9B loaded).
24. Claude security audit (2026-11-07, branch claude/awesome-jackson-45840e): skill `.claude/skills/claude-security-audit`
   (`scripts/audit.py`, standard library; state and reports in `%LOCALAPPDATA%\claude-security-audit`, outside every
   repository). Baseline run on this machine: 2 high, 6 medium, 7 low, 9 info.
   - High: identity in two committed docs; Claude can read 5 credential files.
   - Medium: secret-file patterns not denied everywhere; no CLAUDE_CODE_SUBPROCESS_ENV_SCRUB; Desktop transcripts kept
     forever; CLI 2.1.302 and Desktop's Claude Code 2.1.317 behind 2.1.319, which fixes four permission problems; four
     allow rules that admit any code (`Bash(uv run *)`, two `python -c ' *` rules, a PowerShell one-liner with a
     wildcard) in `.claude/settings.local.json` of both the main checkout and the worktree.
   - Low: LITELLM_MASTER_KEY and ORCHESTRATOR_BEARER in plain text in that git-ignored file.
   - OSV: no advisory for the 7 packages checked.

   Fixed that day by `scrub --apply`: the Windows user name in docs/plans/AGENT-FILE-ISOLATION.md and
   docs/knowledge/agent-file-isolation.md, and an email and two home paths in old Claude memory notes. The owner's
   short name was removed from one note by hand. Kept on purpose: the claude.ai-synced job-search skill.

   Written the same day:
   - The standing rule in `~/.claude/CLAUDE.md` (marker `claude-security-audit:identity-rule`), and AGENTS.md rule 10.
   - The desktop scheduled task `claude-security-audit`: Mondays at about 09:43, saved in Auto mode. Its prompt stops
     with "not on main yet" until this branch is merged.

   Not changed (reported to the owner): settings; the computer name in 45 committed files (machine profiles are named
   after it); 3 pushed commits with the account email.

   Verified:
   - 19 unit tests, 210 passed in total, run as `uv run --with pytest python -m pytest -q`, because Smart App Control
     blocked the pytest.exe launcher.
   - A leak check of every output file (no identifiers, no account UUIDs).
   - A fresh-agent run of the skill. It found nine problems, all fixed: `scrub` and `collect` disagreed on which
     repositories they cover, and changelog lines were cut without notice.

   Not verified: a scheduled run end to end (it needs the merge), and the per-checkout fix advice on a repository
   other than this one.
25. Usage tab for every model (2026-11-07, branch claude/usage-all-models). The tab reads gateway traces plus one record
   per model call made elsewhere (`traces/usage/<source>/<date>.jsonl`, stacklib/usage_log.py):
   - voice typing's Whisper (live previews re-read the phrase so far: shown under the table, not in the totals);
   - the recordings MCP server (client Claude Desktop);
   - ComfyUI jobs, which the tray reads from ComfyUI's GET /history each poll while it runs (high-water mark in
     `traces/usage/comfyui/state.json`; jobs finished just before a ComfyUI restart are lost);
   - `stack.py bench` and the warm-up (source ollama).
   Rows show tokens, audio (x realtime) or images by kind. Gateway traces now carry data_class and location, and outside
   API rows end in "· API". Retro, the orchestrator and smoke send User-Agent agent-stack-<id>. Open WebUI's document
   embeddings go through the gateway on fresh installs. `stack.py usage` prints the tab. AGENTS.md rule 11 and
   tests/test_tray_coverage.py make new services, profile sections and model calls show up in the tray.
   On this box (30 days of real traces): qwen3.5:9b 175 requests. Also claude-sonnet-5-5, 13 requests ($0.13, Open
   WebUI), and claude-haiku-5-5, 2 requests (orchestrator), both from before the private-only build.
   Not counted, and named in the tab:
   - Open WebUI's own speech-to-text: its database has audio.stt.engine "", so the chat mic runs Whisper base inside
     Open WebUI (open item 26 moves it to voice typing's Whisper once `media provision` runs);
   - Open WebUI's document embeddings: its database still has rag.embedding_engine "ollama", until `media provision`;
   - Kokoro, when it runs.
   Claude Code profile A is outside the stack.
   A code review's seven findings were fixed:
   - ComfyUI collection is locked and de-duplicated by job id;
   - an odd job cannot stop the tray's poll;
   - records keep only an error's type, and paths are scrubbed;
   - previews are kept out of the totals;
   - a failed write is retried, and a lost state file does not duplicate jobs;
   - RECORDING_OFF stops programs that were already running;
   - no embedding rows are written without LITELLM_MASTER_KEY.
   Verified:
   - unit tests;
   - a hidden render of the tab built from this worktree, with copies of the main checkout's gateway traces and
     synthetic usage records (table, tiles, chart and notes read back through Tk; no screenshot);
   - the engine tests in the dictation venv;
   - Segment.tokens in both Whisper venvs;
   - the coverage test failing on a probe file.
   Not verified: a live ComfyUI job (its history was empty), live dictation or recording records, the tab's look, and
   Open WebUI embeddings through the gateway on this install (not provisioned).
   After merging:
   - restart the tray from the main checkout;
   - Stop and Start the Voice typing row;
   - run `stack.py whisper install` and restart Claude Desktop (recordings);
   - run `stack.py media provision` and restart Open WebUI (embeddings);
   - restart the orchestrator (its name in the traces).
26. Open WebUI's microphone on voice typing's Whisper (2026-11-07, branch claude/competent-mccarthy-a81053, PR #41).
   - Endpoint: voice typing's control port (8790) also serves an OpenAI-compatible `POST /v1/audio/transcriptions`
     (stacklib/dictation/transcriptions.py). It takes multipart `file`, `model` (ignored), `language`, `prompt` and
     `response_format` json|text. The Origin and Host refusals stay. Bodies may be chunked, because Open WebUI's
     aiohttp streams the file.
   - The key is voice typing's own bearer, DICTATION_BEARER in .env, not the gateway's master key. While voice typing
     is off, any local program could listen on 8790 and would learn only this key. The installer generates it;
     `media provision` appends it to an existing .env and leaves the rest of the file as it is. The app reads it on
     each request, so a key added later works without a restart.
   - Limits: 25 MB per upload, 30 minutes of decoded audio, one request at a time (the next waits up to 2 minutes,
     then gets 503 busy), and 2 minutes to send the body. A refusal is answered first; the server then reads what the
     caller still sends, so the caller sees the answer instead of a reset.
   - No language field means detect it, as OpenAI's API does, even when dictation.language names one. Open WebUI sends
     its user's Speech-to-Text Language when one is set.
   - It runs on voice typing's own Engine (one model, one decode at a time). Each call is recorded under source
     voice-typing with the client named from its User-Agent (Open WebUI).
   - Open WebUI points at it only while `services.dictation` is native. A fresh install gets the environment
     (AUDIO_STT_ENGINE=openai, base URL `http://127.0.0.1:8790/v1`, key, model, request format multipart).
     `stack.py media provision` writes the same five rows into an existing database, after a backup, in one
     transaction. Open WebUI reads them on every request, so it needs no restart.
   - The Usage tab's "own speech-to-text" note stays while audio.stt.engine is "" and goes once the engine points at
     voice typing. A second note names an engine or URL outside the stack.
   - This install (read-only check that night): audio.stt.engine "", audio.stt.openai.api_base_url
     "https://api.openai.com/v1", no key, whisper_model "base". Changing the engine alone would have sent recordings
     to OpenAI.
   - No ffmpeg on PATH, so Open WebUI skips its pydub conversion and forwards the browser's recording unchanged. PyAV
     17.0.0 in the dictation venv decodes webm/opus, ogg/opus, ogg/vorbis, wav, m4a/aac, mp4/aac, mp3 and flac. Broken
     files get a 400; a truncated webm decodes as far as it goes.
   A security review (subagent, read-only) found no critical or high issues. It found three medium ones, all fixed:
   - uncapped decoding: a 494 KB FLAC of digital silence declares 45 minutes, and 25 MB of it would decode to about
     9 GB of samples;
   - a long job holding voice typing's model;
   - the master key reused as the endpoint's key.
   It also found three low ones and one info. Fixed: resets on refused uploads, folder paths in the 503 message, a
   body that trickles in, and dictation's language forced onto Open WebUI recordings. Not done:
   - SO_EXCLUSIVEADDRUSE on the port, because on Windows it can refuse a re-bind while the port's connections are in
     TIME_WAIT, and the tray's health check leaves those every 10 s;
   - a limit on concurrent connections. Local programs could already hold threads before this change.
   Verified:
   - unit tests (309 passed), and the decoder and engine tests in the dictation venv;
   - a throwaway server on port 8797 with the real Engine (large-v3-turbo on cuda, loaded in 5.5 s). Requests were
     sent the way Open WebUI 0.12.3's `_transcribe_openai` sends them, from its own Python 3.11 with aiohttp 3.14.3
     (chunked). webm, ogg, mp4, m4a, mp3 and wav each returned the spoken sentence. Each took 0.3 s warm for 4.8 s of
     eSpeak speech, and the first took 1.1 s;
   - "English" as a language got a 400, and Open WebUI's retry without a language worked;
   - a wrong key got a 401 in OpenAI's error shape;
   - the server wrote six records with client Open WebUI and device cuda, to a temp folder;
   - after the review fixes, the same check with the decoder written here passed again. A German eSpeak recording sent
     without a language came back as German with dictation.language "en". `bomb.flac` (45 minutes of silence) got a
     413 in 12 ms from its header. A 90 s webm muxed live, with no duration in its header (as MediaRecorder writes it),
     got a 413 after 0.4 s with the cap lowered to 60 s;
   - `stack.py media provision` with the real machine profile against a synthetic Open WebUI database in a temp folder:
     16 rows written after one backup, and the note gone.
   Not verified: Open WebUI itself calling it, a real browser recording, and the mic in the browser. The services were
   down, and Open WebUI's live database was not changed: `media provision` needs the owner's OK.
   After merging:
   - run `uv run scripts/stack.py media provision` from the main checkout. It adds DICTATION_BEARER to .env, backs up
     webui.db, and writes the rows;
   - restart voice typing (Stop and Start its tray row) so it serves the endpoint.
   If voice typing is later turned off, Open WebUI's mic shows a connection error until its engine is set back to
   Whisper (Local) in Admin Settings > Audio. Neither the tray's Voice typing switch nor provisioning undoes the rows.
27. Refine selected text (2026-11-07, branch claude/ai-text-refinement-contextmenu-70d19f): a pencil button left of
   the mic and Ctrl+Alt+R copy the selection of any app, have `local-primary` rewrite it in a style (7 built in, your
   own under `refine.prompts`), check the reply, copy again to confirm the same selection and paste over it. Every
   suggestion goes to `.run/dictation/refine-log.jsonl` (before, after, status); Revert and History are in the pencil's
   right-click menu. Design: docs/design/plans/2026-11-07-refine-selection.md. Verified: 59 new unit tests (260 in
   total); a test copy of the app (port 8791) with a test gateway (port 4010) refined, reverted and refused "nothing
   selected" in a Win32 EDIT control (HTTP, injected hotkey, a real click on the pencil), in a throwaway Word document
   over COM and in Edge textarea and contenteditable fields; the clipboard was put back every time. A code review then
   found and the session fixed two menu bugs, an Esc stall and five smaller ones; the EDIT-control, Esc and menu runs
   passed again afterwards, the Word and Edge runs were not repeated (the permission check refused the rerun). That evening the
   owner's tray had stopped all its services at about 23:07, from outside this session; they were left stopped. Not
   verified: Logseq and Notion themselves, the look of the bar and the History window, the tray's new settings group
   live. The live app runs the new code only after the tray restarts from the main checkout.
   2026-11-08: the owner asked for the log to be kept only temporarily. Entries now expire after
   `refine.keep_minutes` (30; tray: Keep refine history for), are hidden at once and deleted from the file within a
   minute (prune at start, before each entry, and every 60 s); the file goes with its last entry. Unit tests only
   (66 in tests/test_refine.py); not yet run in the live app.
   2026-11-08 (branch claude/text-refinement-hotkey-menu-fdb127): **Ctrl+Alt+Shift+R** (`refine.menu_hotkey`, tray:
   Refine style menu hotkey) opens every refine style in a menu at the text caret (GetGUIThreadInfo; the mouse pointer
   where an app draws its own caret), numbered 1-9, plus Revert. The pick refines in the window the hotkey was pressed
   in (Refiner.start/revert take a target). A 1-pixel invisible window takes the front so the menu gets the keyboard
   and closes on a click elsewhere; focus goes back to the app when it closes. The key was free here (RegisterHotKey
   probe). Verified: unit tests; a harness in the voice typing venv with a stub app opened the real menu, a scripted
   "2" key picked Fix spelling and grammar only with the right window, Esc returned focus. Not verified: the live
   app's hotkey, the menu's look, the caret position in Word, Logseq and Notion.
28. Privacy cleanup (2026-11-07, branch claude/personal-info-cleanup-0f23d8). The repository is public, and
   it named the computer and the Windows account. Now machine profiles are local: `machines/*.yaml` except
   `_defaults.yaml` is ignored, the installer writes the profile, and a linked worktree reads the main checkout's
   (`profile.machine_file`). Docs say "the reference machine", `<owner>` and `machines/<HOST>.yaml`, and the generated
   LiteLLM header no longer names the machine. `tests/test_personal_info.py` checks every file git would publish for
   this machine's names and git email, plus words in the ignored `.personal-terms`. The stray `litellm.db*` (an Open
   WebUI database committed 2026-10-26) is gone; it held the live LITELLM_MASTER_KEY, so the key must be rotated (.env,
   Open WebUI's connection, `~/.openclaw/.env`). The main checkout's profile has uncommitted Settings edits, and a
   plain pull refuses to remove it, so before pulling: copy `machines/<HOST>.yaml` out of the repository,
   `git checkout -- machines/<HOST>.yaml`, pull, copy it back (tested on a scratch repo; `git rm --cached` first makes
   the pull refuse instead). Not done: git history, GitHub's pull request pages and three commits' author email still
   carry the names. Same day: 26 branches deleted on GitHub (25 merged, plus the superseded
   multimodal-stack-planning-s1 at c5d9a7e) and 20 locally (four subagent worktrees removed; four idle session
   worktrees detached, files kept). `claude/ux-rules-research-skill-a11269` stays for its unmerged `a8400c9`.
29. Process names (2026-11-07, branch claude/pas-process-naming-bc10e1). Every process the stack starts runs as
   `PAS-<Name>.exe` (stacklib/procname.py): Tray, Phoenix, LiteLLM, Orchestrator, ComfyUI, Kokoro, OpenWebUI,
   VoiceTyping, Recordings (Whisper MCP), Supervisor (Task Scheduler), Installer (setup worker). Each is a copy of its
   venv's base python(w).exe plus DLLs in `<venv>\pas\`, so one process replaces launcher + child interpreter. The
   orchestrator now starts on .venv's Python directly, not `uv run`. Task Manager's Processes tab shows the file's
   description and icon: copies get "PAS-<Name>" and the tray icon only where Smart App Control is off, because writing
   them unsigns the file. Here (SAC on) copies stay byte-identical: Details tab, tasklist and the tray's Resources tab
   show PAS names; the Processes tab still says "Python". A refused copy (WinError 4551) falls back to the plain command
   and its folder stays signed-only. Tray and setup windows carry the tray icon; Start menu and login shortcuts are
   rewritten to PAS-Tray.exe with that icon. Off switch: AGENT_STACK_PROCESS_NAMES=0 (AGENT_STACK_PROCESS_ICON=0 for
   branding only). Verified: unit tests; a branded copy's resources read back (FileDescription, icon, unsigned; not
   run here); a PAS-Orchestrator.exe from the worktree venv ran as one process under SAC and imported the orchestrator.
   Not verified: the live tray and services as PAS processes, branded copies running on a machine without SAC, Linux
   (unchanged). After merging: restart the tray through `stack.py tray` (rewrites the shortcuts), rerun
   `stack.py whisper install` and `stack.py tasks install` if used, so their saved commands name the PAS copies.
30. Installer features and the tray's Features card (2026-11-07, branch claude/installer-features-resources-0e9481).
   - `stacklib/features.py` holds the catalog, the load estimates, the fit check and each feature's status, read from
     the system. Required: local models, gateway. Optional: Open WebUI, Phoenix, images, voice typing, recordings in
     Claude Desktop, OpenClaw.
   - The installer's page 1 is "Which features do you want?": one row per feature with disk, GPU memory, GPU work,
     CPU and RAM on this PC, and a box that adds up the choice. Page 2 holds the folders; the media folder shows only
     for images or recordings.
   - `install.save_features` writes services.open_webui, comfyui and dictation, observability.phoenix and media.root.
     It never turns off a feature that is installed and on.
   - New setup step `recordings`: Whisper for Claude Desktop, registered after a backup of its config.
   - The tray's Overview has a Features card. A service row says "Not installed" when its program is missing. **Add
     features...** (card and menu) opens the installer.
   - `stack.py features [--details]` prints the same.

   Measured for the estimates on this box (2026-11-07):
   - uv tool environments: litellm 0.57 GB, arize-phoenix 0.54 GB, open-webui 1.94 GB;
   - ComfyUI 16.8 GB (venv 4.5 GB, models 12.2 GB);
   - Whisper environments: voice typing 0.25 GB, recordings 2.38 GB; large-v3-turbo is 1.62 GB in the HF cache;
   - OpenClaw 0.50 GB;
   - a running LiteLLM: 0.3 GB working set;
   - qwen3.5:9b at 32k: 6,166,413,310 bytes on the GPU (5.7 GB of 2**30).

   Not measured (estimates in the code): the memory of Open WebUI, Phoenix, ComfyUI (idle and after a job), voice
   typing, the recordings server, OpenClaw, the orchestrator and the tray. Only Ollama was running that night, and
   another LiteLLM process was up, so no service was started to measure them.

   Verified:
   - unit tests (322 passed);
   - the installer window built hidden in tests: locked rows, the summary following the ticks, Back and Next keeping
     the ticks, Install writing the choice and starting the plan (mocks);
   - renders of both installer pages and the tray's Overview from this worktree, with this PC's real status and with
     a fake fresh PC. A 700 px screen scrolls the features page and keeps the buttons in view; the scrollbar is
     mapped (geometry checked) but does not show in the capture;
   - `stack.py features --details` on this PC;
   - the terminal feature question, with scripted answers and every write stubbed.

   A code review's findings were fixed:
   - a recordings entry already in Claude Desktop is never rewritten;
   - a worktree adds none;
   - a failed check ("Not checked") leaves the feature's switch as it is;
   - a feature that is on but broken is ticked for repair;
   - the page scrolls on short screens;
   - the terminal installer re-asks after a typo;
   - the orchestrator's row never reads "Not installed";
   - a failed `uv tool dir` is retried;
   - Claude Desktop's config is read even with a byte order mark;
   - doctor's GPU baseline is capped at 2.5 GB;
   - images with only a model missing count only that model.

   Not verified:
   - a real install run with the new page (a fresh PC, or adding a feature here);
   - the recordings step for real (Claude Desktop's config);
   - Add features from the live tray, which runs the main checkout's code;
   - the terminal installer's feature question, typed by hand;
   - Linux and macOS.

   After merging, restart the tray from the main checkout.

   2026-11-08, same branch: drop-downs under four features set what they install with (chat model and context,
   image size and steps, Whisper model and hotkey for voice typing, Whisper model for recordings); the estimates follow
   each change and `install.option_edits` writes only changed values. Seen on this PC that morning, through the
   page: the main checkout's new local profile (written fresh after the privacy cleanup untracked the old one) had
   no model override, so setup pulled the class default qwen3.6:35b-a3b-coding (30.9 GB) and voice typing was off; the
   page flags the 35B as not fitting next to the other features (11.4 GB of GPU memory against 9.5 GB free), and the
   recordings entry in Claude Desktop still points at the old D: drive ("Files missing"). Voice typing was reinstalled
   under C:\media\dictation by then and worked. Picking qwen3.5:9b in the drop-down restores the earlier primary.
31. GitHub account name in the security audit (2026-11-08, branch claude/dazzling-brattain-729c88): kind `owner-login`.
   Sources: gh (local config, `gh api user` when online), a no-reply git address, `logins` in identity.local.json, and a
   github.com origin owner only when it matches one of them or owns the current repository. `scrub` turns links to
   the repository's own PRs and issues into `PR #N` / `issue #N` and other mentions into `<owner>`, in prose and
   Claude's files; code and config are reported (IDENTITY-LOGIN-CODE). Verified: unit tests with a made-up login;
   a dry run here found the 27 hits in 10 files that PR #46 then removed by hand, and `collect` also found the name in
   Claude's own instruction files (not changed: `scrub --apply --local-only` fixes them). Not verified: a scheduled
   run; the live scheduled task's prompt still lacks the new "GitHub account name" wording in scheduled-task.md.
32. Installed app apart from the repository (2026-11-08, branch claude/installation-app-independence-db332c).
   Before this, every path came from the folder the code ran from, so the installed stack's tray log, pid files,
   `.run` data, traces, `.env`, profile, generated configs, the Start menu and login shortcuts and Claude Desktop's
   recordings entry (its AGENT_STACK_USAGE_DIR) all lived in or pointed at the checkout. Open WebUI's database also
   stores each upload's absolute path (`file.path`).
   - `install.cmd` (and `stack.py install|setup` from a checkout) now runs `stack.py deploy` first
     (stacklib/deploy.py). It copies the git-tracked files without tests/ into `%LOCALAPPDATA%\Programs\AgentStack`
     (AGENT_STACK_HOME or `--to` override it) and builds the app's own signed `.venv`. It brings `.env`, the profile,
     `.run` (without pids, logs, install), traces and orchestrator/data over once, only where the app has none
     yet, and rewrites the source paths in the copied SQLite databases. Then the installer opens from the app.
   - Before copying, deploy stops the checkout's tray and services and an earlier install's. A reinstall overwrites
     the code and removes the files the source dropped (`.agent-stack-files.json`). It keeps the app's data and
     `memory/`.
   - Marker `.agent-stack-app.json`: it also records the "checkout is behind origin" warning for the app's installer.
   - New setup step **Point Claude Desktop and start-up entries at this app**: it re-registers local-whisper when
     its entry differs, rewrites the Linux autostart file, and warns about scheduled tasks registered from another
     folder.
   - `stack.py tray`, `start.cmd` and `stop.cmd` in a checkout hand over to the installed app; `--here` keeps the
     old in-checkout behaviour for development.
   Verified:
   - unit tests;
   - a copy of this worktree into a temp folder: `make_venv` built a signed `.venv` there, the copy reported
     itself as the app, `stack.py tray --status` in the worktree handed over to it, then the temp folder was
     deleted.
   Not run: install.cmd end to end on this machine, because it would stop the live tray and copy the main
   checkout's data.
   After merging, run install.cmd from the main checkout once. Then check that the Start menu entry and the login
   shortcut start `%LOCALAPPDATA%\Programs\AgentStack`, and that Open WebUI shows the old chats and images. Then
   restart Claude Desktop (recordings). Delete the checkout's `.run`, `traces` and `.env` when the app works.
33. Tray GPU card lists every model on the card (2026-11-08, branch claude/whisper-gpu-memory-44134a). It was
   "GPU: loaded in Ollama" and asked only Ollama, so voice typing's Whisper (loaded on cuda that day, ~1.2 GB) and
   ComfyUI's models never showed. Now "GPU: loaded models" (stacklib/gpu_models.py) adds a "Used by" column and merges
   Ollama's /api/ps, voice typing's /health (size is the measured figure per model, shown with ~; new health fields
   idle_s and unload_after_min give "Unloads") and ComfyUI's /system_stats torch_vram_total (listed above 256 MB).
   Not listed: the recordings server's Whisper inside Claude Desktop (no port to ask). Verified: unit tests; rows built
   from the live services (qwen3.5:9b 5.7 GB + whisper large-v3-turbo ~1.2 GB; nvidia-smi 9.1 of 12 GB used); the
   card's rows rendered in a hidden Tk frame. Not verified: the live tray (restart it from the main checkout after
   merging; restart voice typing for the Unloads column).
34. Models folder vs the Ollama app's Model location (2026-11-08, branch claude/voice-typing-manual-command-3e6665).
   After install.cmd the tray showed "Models missing" although `ollama list` had all three models: the new profile
   named ~\.ollama\models, but the Ollama app's own Settings > Model location (`%LOCALAPPDATA%\Ollama\db.sqlite`) is
   D:\ollama\models, which wins over OLLAMA_MODELS, so the pulls went to D:. Now:
   - the Features card asks the running Ollama (/api/tags, cached 5 s) and falls back to manifests in the folder
     Ollama really reads; a profile that differs from the app's setting shows as a warning on the row;
   - the installer offers the app's folder first (with a note), refuses another models folder while the app setting
     differs, and `stack.py setup` adopts it and writes it into the profile;
   - the move step does not move models where Ollama would not read them, and the env step warns.
   Verified: unit tests (tests/test_ollama_location.py and the full suite); on this PC, read-only, the status reads
   Installed with the override note and the installer's default is D:\ollama\models. Not run: the installer itself.
   This PC's profile still says ~\.ollama\models: rerun install.cmd (it now offers D:) or set the folder in Settings.
15. Installer (2026-11-01, branch claude/interactive-installer-paths-77aabe): `install.cmd` / `stack.py install` asks for the models
   and Python tools folders, then runs setup in a detached worker (state in `.run/install/state.json`). That day drive D:
   (USB SSD) was not connected, so OLLAMA_MODELS=D:\ollama\models broke every pull. Verified with unit tests, a render
   harness and a stand-in worker; the real worker (registry, Ollama restart, pulls) has not run yet.
