# Stack state (mutable; machine facts, measurements, open items)

Updated: 2026-11-09 (speech models beside Whisper, and the installer's system check; open item 41). Before that,
2026-11-08 (Thai voices for read aloud, Kokoro Thai; open item 40). Before that, the same day (Mandarin
voices for read aloud, Kokoro v1.1-zh; open item 39). Before that, the same day
(blocked sites for Open WebUI's web reading, and audit checks for Claude; open item 38). Before that, the same
day (the installer's catalog in config/installer.yaml, install and remove from the tray and the
installer, the tray's Overview and Settings reworked; open item 37). Before that, the same day (read aloud of selected
text, an optional part of voice typing; open item 36). Before that,
the same day (voice typing history kept for dictation.keep_minutes; open item 35). Before that, the same day (the installer makes an app apart from the repository; open item 32). Before that, the same day (the installer asks which features to install, with their load on this PC, and the tray's Features card; open item 30). Before that, 2026-11-08 (voice typing's cleanup prompt is a setting; open item 23). Before that, 2026-11-07 night (PAS-<Name> process names; open item 29). Before that, the same night (privacy cleanup, machine profiles local; open item 28). Before that, the same night (refine selected text in every app; open item 27). Before that, the same night (Open WebUI's microphone on voice typing's Whisper; open item 26). Before that, 2026-11-07 late evening (the Usage tab counts every model the stack runs; open item 25). Before that, 2026-11-07 (Claude security audit skill and standing identity rule; open item 24). Before that, the same day (voice typing in every app; open item 23). Before that, 2026-11-03 (tray Hugging Face / OpenClaw rows, OpenClaw gateway setup; open item 17). Before that, 2026-10-26 evening (B-S0 spike and B2b supervisor; Phoenix blocked by Smart App Control). Before that, 2026-10-25
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
   2026-11-08 (branch claude/refine-copy-button): refine no longer puts text on the clipboard by itself. The result
   bubble has a **Copy** button (also when nothing was replaced, and **Copy suggestion** for a rejected reply); the
   pointer over the bubble holds it open. `refine.auto_copy` (tray: Copy refined text to the clipboard, off by default)
   puts every refined text there, replaced or not. Not-replaced refines are logged as `skipped` and Revert still finds
   them. Verified: unit tests (590 passed); a Tk harness in the voice typing venv (button shown, click copied and read
   "Copied", hover paused the hide, the bubble dropped the text when it closed). Not verified: a refine in the live app.
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
35. Voice typing history (2026-11-08, branch claude/voice-typing-history-edd081). Each dictation that produced text
   goes to `.run/dictation/voice-history.jsonl` (stacklib/dictation/voicelog.py, the refine log's store): app, window,
   the transcript as heard, the text typed, status, seconds of speech. Entries expire after `dictation.keep_minutes`
   (30; tray: Keep voice typing history for, applied through `POST /reload` without a restart) and are pruned at
   start, before each entry and every minute, like the refine log. The mic menu's **Voice typing history...** opens
   a window (history.VoiceHistoryWindow: heard vs typed, Copy, Type again in the app); Paste last text again and Copy
   last text now read the newest kept entry instead of an in-memory list of 10, so they grey out on expiry.
   Verified: unit tests (tests/test_voice_history.py, the hidden window included); `_remember`, `copy_last` and the
   prune run in the voice typing venv against a stub app. Not verified: the live app, a real dictation, the window's
   look. The live app runs the new code only after a restart from the main checkout (or the installed app).
36. Read aloud (2026-11-08, branch claude/read-aloud-highlighted-text-57ce4d; design
   docs/design/plans/2026-11-08-read-aloud.md). An optional part of the voice typing app: a speaker button right of
   the mic (bar order pencil, mic, speaker, as the owner asked), Ctrl+Alt+S, Esc while it reads, a right-click menu
   (pause, read it again, voice picker with a sample, speed, voice per language), a tray Settings group "Read aloud"
   and Show/Hide speaker. `read_aloud.enabled` is off by default; the installer's feature **Read aloud (Kokoro)**
   (requires voice typing) or `stack.py read-aloud install` adds espeakng-loader 0.2.4 and comtypes 1.4.17 to voice
   typing's environment and downloads Kokoro-82M ONNX (pinned revision 1939ad2a) into HF_HOME.
   - Voices: Kokoro on the CPU (fp32 default; int8 as fast, 0.3 GB instead of 0.5 GB of RAM) and Windows' SAPI and
     OneCore voices (here only English: David, Zira, Mark). Usage records: source read-aloud, kind speech.
   - Measured: Kokoro 3-3.5x real time on 6 threads, load 1.2-2.3 s; first speech 2.1 s cold in a test copy of the
     app. Whisper heard the output back word for word.
   - Already on this PC from the spike: Kokoro fp32, fp16 and int8 weights and four voices in D:\huggingface (about
     0.6 GB); the install step fetches the rest of the voices.
   - Verified: unit tests (58 in tests/test_read_aloud.py, one in the installer window tests; 573 in total); a test copy of
     the app on port 8797 writing WAV files (bubble, states, pause, resume, stop, voice sample, hide and show, usage
     records); the WinMM player with silence.
   - Not verified: sound through the speakers; read aloud installed into C:\media\dictation and the live tray (not
     run: it changes the live environment); a real selection read with the button or hotkey; Kokoro's other languages
     by ear.
   - After merging: rerun install.cmd from the main checkout and tick Read aloud (or `uv run scripts/stack.py
     read-aloud install`), then Stop and Start the Voice typing row; the tray shows its new group after a restart.
   - Same day, after the owner tried it (the speaker worked, the tray's Kokoro row said "Not available yet", it felt
     slow): `read_aloud.device` auto|gpu|cpu (tray: Runs on; installer option). GPU = onnxruntime-gpu 1.31.1 (CUDA 13)
     + nvidia-cudnn-cu13 9.28.1.4 (no deps) + Ollama's lib/ollama/cuda_v13, about 0.8 GB, added by `read-aloud
     install` for gpu or auto on an NVIDIA PC (it stops voice typing while it swaps onnxruntime). Measured: 0.3-0.4 s
     per sentence, 1.0 GB VRAM. DirectML failed on Kokoro's ConvTranspose. Pieces are sentence-sized and made ahead in
     parallel (two on the CPU sharing six threads: 4.3x real time against 3.3x; one on the GPU), up to 30/60 s ahead,
     one at a time while the CPU is over 85% busy; Kokoro loads while the selection is copied and on hover. Read it
     again replays the last reading's audio from memory (64 MB cap), no model run. The tray's Kokoro row now shows
     read aloud's state and carries Hide/Show speaker. Verified: unit tests (72 in tests/test_read_aloud.py, 599 in
     total); the real Speech and Reader in a throwaway venv, sound into WAV files at real-time pace: first speech
     0.85 s on the GPU and 1.74 s on the CPU, no gaps between the 7 pieces on either, replay made nothing. Not
     verified: the tray row live.
   - Same day, pauses: each sentence is its own piece, the voices' own silence is trimmed to 40 ms (Kokoro left 0.3 s
     before and 0.4-0.7 s after each sentence), then read_aloud.pause_sentence_ms 300, pause_item_ms 600 (list items,
     headings, table rows), pause_paragraph_ms 1000, and break_ms 1500 every break_every 5 sentences in a row within a
     paragraph (tray: Read aloud > Show advanced). Measured in a WAV: 0.38 / 0.68 / 1.04 / 1.58 s.
   - Found on this PC: C:\media\dictation\.venv has both onnxruntime and onnxruntime-gpu 1.31.1, the CPU build's files
     on top, so CUDA is gone and Kokoro runs on the CPU. Cause: faster-whisper depends on `onnxruntime`, so a voice
     typing install puts the CPU build back. Fixed in code: a mixed install counts as not installed, `read-aloud
     install` removes the CPU build and reinstalls the GPU one, and the voice typing install restores the GPU build
     after faster-whisper. Not run here: rerun `uv run scripts/stack.py read-aloud install` (it stops and restarts
     voice typing).
37. Installer catalog, install and remove, tray rework (2026-11-08, branch claude/installer-config-ui-refactor-c81bdc).
   - Catalog: `config/installer.yaml` (read by stacklib/catalog.py) holds every version, URL and model list the
     installer used to hard-code: the uv tool pins, Ollama's and Node.js's winget ids and pages, `openclaw@latest`,
     the ComfyUI repository and image model files, the Whisper models and repositories, Kokoro's repository, revision,
     variants and voices, voice typing's, read aloud's and the recordings server's package pins, the winget package
     lists, the drop-down choices, and each feature's measured footprint. `model_catalog` moved there from
     machines/_defaults.yaml (profile["catalog"] still has it). The derived constants were compared with the old
     literals: identical; the regenerated winget files differ only in their header line.
   - Remove: stacklib/uninstall.py plans (what goes, sizes, what stays) and removes a feature: Settings' switch off
     through settings.apply (stops it, restarts what depends on it), then `uv tool uninstall` (Open WebUI, Phoenix),
     the ComfyUI folder, voice typing's .venv, read aloud's packages (the CPU onnxruntime goes back), the recordings
     folder and Claude Desktop's entry (backed up), `npm uninstall -g openclaw`, and Hugging Face model folders no
     other installed feature uses. Open WebUI's microphone goes back to its own Whisper when voice typing goes, and its
     image button off with ComfyUI. Chats, traces, images, transcripts, OpenClaw's settings and the machine profile
     stay. Deletes are guarded (drive roots, home, the app folder, media outside allowed_roots, HF folders outside
     hub/models--*). Ollama models: Download and Remove (refused while Settings names the model).
   - The setup worker runs removals as steps (Plan.remove, remove_models, pull_models, only, targets; plan_steps),
     and reads the profile again before each step. The tray's Features card has Install / Repair / Remove per feature
     and Download / Remove per model, starts the worker for that one feature (install.start_feature, start_removal,
     start_download), shows its step and progress, and when a run ends reads the profile again and starts what was
     turned on. The installer's page 1 has a Remove column and "Not used by the stack, delete" for models; Apply
     changes asks first.
   - Tray: Services rows are named by module (Local models, Gateway, Agent tools, Chat in the browser, Trace viewer,
     Image generation, Voice typing, Read aloud) with the program on the line below, two action columns (Open / Hide /
     Show; Start / Stop, blank where not the stack's), one row per Ollama runner process with its pid and Unload, and a
     Recordings row for Claude Desktop's Whisper server. The Hugging Face card became Storage (stacklib/storage.py):
     every model, program and data folder, per drive. Settings groups are cards. Buttons have a fill and outline; the
     destructive ones are outlined in the danger colour; confirmations name what is lost, with the safe button
     focused (the stock "Restart Ollama?" box is gone too).
   - Measured on this PC: storage scan 4 s (32 s with os.walk + lstat); 73.8 GB in all (Models 50.2, Programs 15.1,
     Data 8.4; C: 35.7, D: 38.1). Not used by the stack: qwen3.6:35b-a3b-coding 22.6 GB, google/siglip2 4.6 GB and
     facebook/dinov2 0.35 GB in D:\huggingface, the media uv cache 8.4 GB. Ollama's runner matched to its model through
     the manifest (llama-server child of `ollama serve`, `--model <store>\blobs\sha256-...`): 52 ms per poll.
   - Verified: unit tests (37 new in tests/test_catalog.py and tests/test_uninstall.py); renders of the tray's
     Overview, Settings and the remove dialog in both themes, and of the installer's pages, from this worktree with
     real read-only status and every start, stop and setup patched out; a dry run of every removal plan on this PC.
   - Not verified: a real install, repair or removal through the worker (nothing was installed or deleted here), the
     live tray (it runs the installed app's code), the installer's new Remove column clicked by hand, pids of the
     stack's own services in a render (the worktree has no pid files).
   - A code review (subagent, read-only) found no critical issue, 3 high and 8 medium ones, all fixed: removal now
     plans and checks every folder before it changes anything (shape: ComfyUI's main.py, a venv's pyvenv.cfg, the
     server script, hub/models--*; strictly inside an allowed root; no outputs, inputs, transcripts or HF cache
     inside a folder that goes), waits for programs to let go, deletes the program folder last, resets Open WebUI's
     microphone first, retries locked files, and reads Claude Desktop's config with a BOM; the tray's Install refuses
     before writing the profile when a setup runs; an unexpected error no longer leaves every button disabled; Unload
     acts on the model it showed; Start and Stop wait while setup owns a service; the installer no longer touches Tk
     from a thread and always measures before it asks. Also found and fixed here: the Unload button called a function
     that did not exist (media.unload_model).
   - Recordings for Claude Desktop retired the same day, at the owner's word ("this app should not have any dependency
     with non-open source software like claude"): no installer step, option, Services row or re-registration; the
     Features card and the installer list it only while an old install is here, with Remove; `stack.py whisper` keeps
     only `unregister`. This PC still has it (Linked, 2.4 GB in C:\media\whisper): Remove it from the tray after
     merging, with Claude Desktop closed. Open question for the owner: the Claude Code tooling around the repository
     (profile B, .claude/agents, the security audit skill) is not part of the installed app and was left as it is.
   - Read aloud in more languages, the same day, at the owner's request ("installation options for best models for
     key languages that kokoro does not cover"). A research subagent compared open text-to-speech models per
     language (licences of weights and training data checked at the source); the owner then chose: offer Piper voices
     fine-tuned from the research-only "lessac" base, marked as such; no GPU-only models for now; keep Windows' voices.
     Built: `voice_packs` in config/installer.yaml (rhasspy/piper-voices pinned at e7229f7), a Piper engine in
     dictation/tts.py on the existing onnxruntime and espeak-ng (no piper-tts, which is GPL-3.0, and no new package),
     `read_aloud.packs` / `packs_dir`, More voices in the installer, Download / Remove rows under Read aloud on the
     Features card (setup worker steps voice_packs / remove_voices), Storage rows, the Settings voice picker, and
     auto-language picking them (Vietnamese detection added). Measured here with the real voices in read aloud's
     environment (downloaded to a scratch folder with the owner's OK, deleted afterwards): load about 3 s; Dmitri and
     VAIS-1000 made 3.3-3.7 s of speech in 0.14-0.15 s, Thorsten (high) 3.8 s in 0.87 s; Whisper (small, CPU) heard
     the German sentence word for word, the Russian and Vietnamese ones with one word off each.
     Not done: Mandarin (Kokoro v1.1-zh with misaki[zh]), Japanese (Kokoro's own voices; misaki[ja] needs mojimoji,
     which has no Python 3.14 wheel), Thai (a Kokoro-based Thai model through FastThaiG2P) and Arabic (Nabra-82M with
     camel-tools): each needs its own text front-end; Cantonese and Korean have only GPU-sized open models (the owner
     said not now); Indonesian has no clean voice. Not verified: the installer's More voices and the tray's Download
     clicked by hand, and a reading in the live app.
   - After merging: rerun install.cmd from the main checkout (it updates the app), then restart the tray.
   - Installer window in the tray's look (same day, branch claude/installer-ui-ux-improvements-5bb01f, on top of this
     work): the palette, system light/dark theme and ttk styles moved from tray.py to stacklib/theme.py, which both
     windows apply (new there: TEntry, Good/Card.Head labels, greyed disabled checkboxes). The installer names its
     three steps at the top (Features, Folders, Install), draws cards, has one accent primary button per page and the
     danger outline on Remove and apply. Page 1: hairlines between features, the status column coloured only for
     state (green working, amber/red to look at), the detail card held at its tallest height (no jump while the
     pointer moves) and set beside Your choice, its load one fact per line. Page 2: folder checks marked ✓/✗ as well
     as coloured, and a **What happens next** card. Progress: one bar for the whole run, a line with the step, its
     percentage or elapsed time, a themed log card, and after the run **Open chat** (Open WebUI on) or **Change
     choices and run again** as the primary button. Verified: unit tests (2 new); renders of every page, the remove
     confirmation, and a running and a failed progress page, in both themes, from the worktree with writes and setup
     patched out. Not verified: the live installer, a 150% display, keyboard traversal by hand.

38. Blocked sites (2026-11-08, branch claude/ban-insecure-web-search-a6dc77). Open WebUI is the stack's one web reader
   (its web search, pasted links, its fetch tool), and stacklib/webfilter.py fills both of its filters from
   policy/web-filter.yaml and the profile's `web_filter:` section (on by default; installer feature **Blocked sites (web
   filter)**, setup step `web_filter`, tray Settings > Blocked sites, `stack.py web-filter`).
   - Lists, in fill order: your own sites; request catchers and tunnels (40, shipped); people-search and data brokers
     (38, shipped); Phishing Army (downloaded daily, 144,330 sites on 2026-11-08, 124,201 after subdomains fold into
     their parents and the `keep:` platforms drop out); Hagezi TIF mini (~190,000, off). URLhaus's public hostfile
     answers 410 Gone, so it is not used. Phishing Army listed docs.google.com whole, hence `keep:`.
   - Page-fetch filter: WEB_FETCH_FILTER_LIST, read at Open WebUI's start, about 24,000 characters (1,219 sites here).
     Web search filter: config row `web.search.domain.filter_list`, read on every search, up to web_filter.max_sites
     (25,000), rewritten by the tray every 10 minutes without a restart; entries the owner added in Open WebUI's admin
     page are kept. Every entry starts with "!" (an entry without it is an allow-list).
   - Measured with Open WebUI 0.12.3's own matcher: 0.83 s per search at 25,000 sites with 5 results, 1.67 s at 50,000,
     4.09 s at 124,279. So only about a fifth of the phishing list fits the search filter by default.
   - Claude side, report only (rule 9): /claude-security-audit gained WEB-BLOCKLIST-RULES (Claude Code WebFetch deny
     rules missing for the list in %LOCALAPPDATA%\claude-security-audit\blocked-sites.txt, which the stack writes),
     WEB-DNS (protective resolver on the adapters that are up) and WEB-SERVER-SIDE (Claude's web search runs on
     Anthropic's servers). `stack.py web-filter export` writes the deny rules (`WebFetch(domain:x)` plus
     `WebFetch(domain:*.x)`, per code.claude.com/docs/en/permissions) and a Chrome URLBlocklist .reg file; the owner
     applies both.
   - This PC: no protective DNS on its adapters (read-only check that day).
   Verified: unit tests (tests/test_webfilter.py and the audit's WebFilter tests); a real Phishing Army download into
   the worktree's .run; the search-row sync on a temp copy of the installed app's webui.db (25,000 entries in 0.48 s,
   a second run unchanged, an owner entry kept, off cleared only the stack's); Open WebUI's own validate_url with the
   generated environment refused x.webhook.site and spokeo.com and allowed github.com and wikipedia.org; `audit.py
   collect --offline` with its state in a temp folder read the stack's 78-site list and reported WEB-BLOCKLIST-RULES
   (78 sites reachable), WEB-DNS low and WEB-SERVER-SIDE, its PowerShell DNS command included.
   Not verified: the live tray and Open WebUI with the filter (the installed app runs the old code until install.cmd
   is rerun), a web search through Open WebUI (web search is still off, M6), the Settings group's look, the .reg
   import into Chrome.
   After merging: rerun install.cmd from the main checkout (the setup step downloads the lists), then consider
   protective DNS for this PC.
39. Mandarin voices for read aloud (2026-11-08, branch claude/jovial-hodgkin-d60cf7, on top of the Piper voices in
   item 37). Kokoro v1.1-zh (onnx-community/Kokoro-82M-v1.1-zh-ONNX at 6cc0f0d, Apache-2.0) is the voice set
   `kokoro-zh` in read_aloud.packs, beside the Piper voices: More voices in the installer, Download / Remove on the
   Features card (setup worker steps voice_packs / remove_voices). Download installs misaki[zh] 0.9.4 and its
   dictionaries (jieba, pypinyin, pypinyin-dict, cn2an, proces, ordered-set, addict, regex 2026.9.29; 131 MB) into
   voice typing's environment, checks that they load, then fetches the weights read_aloud.kokoro names (fp32 339 MB,
   int8 127 MB, sha256 checked), the tokenizer and 8 voices into the HF cache. Remove uninstalls the packages (voice
   typing stopped and started around it), then deletes the cache folder. tts.KokoroZh is a second Kokoro engine
   (same GPU, fallback and idle unload); misaki loads in a thread beside the ONNX session. Voices: kokoro-zh:zf_003
   (default for Chinese), zf_092, zf_088, zf_006, zm_031, zm_037, zm_013, zm_061, shown as "Voice 003 (Chinese,
   Mandarin, female)".
   - Smart App Control: misaki[zh] installed from wheels (jieba is source only; uv built its pure-Python wheel) in a
     throwaway python.org 3.14 venv and imported; regex's `_regex.pyd` loaded (2026.11.8, published that day, and
     2026.9.29, the pinned one). misaki declares Python <3.13; uv ignores that bound.
   - On this PC, with the owner's OK (2026-11-08): the misaki packages are installed in C:\media\dictation\.venv, and
     the model (fp32 and int8) with all 103 voices is in D:\huggingface (497 MB; the stack uses 8 voices). The machine
     profile was not changed (read_aloud.packs does not name kokoro-zh); the tray shows the set as installed.
   - Voices chosen by a Whisper large-v3-turbo round trip of all 100 Mandarin voices: 4 plain sentences (all 100
     right, 97 with no pinyin syllable wrong), then 6 harder ones (tongue twister, polyphones, long sentences: 45 with
     no syllable wrong); ranked by syllable errors, character errors, then Whisper's log-probability. zf_001,
     upstream's sample voice, came last of the female voices. Every voice read 上调 as shàng diào (a pypinyin
     reading, not the voice).
   - Measured through read aloud's own code (tts.Speech, 22.8 s of speech in 4 pieces, one at a time): load 2.1 s on
     the CPU, 2.2 s on the GPU (4.0 and 3.6 s before misaki loaded in parallel); fp32 3.2x real time on 6 CPU threads,
     int8 the same; GPU 10x (0.46-0.56 s per sentence after the first); working set +0.87 GB (fp32) / +0.69 GB (int8)
     with misaki's dictionaries; +658 MiB of GPU memory. First cold load right after the install: misaki took 10 s
     (Smart App Control checking the new files), 1.3 s after that.
   - Verified: unit tests (tests/test_kokoro_zh.py: 31 here, 3 engine tests in voice typing's environment); a test
     copy of the voice typing app (port 8797, machines/zhtest.yaml, speech into a WAV) read a Chinese selection from
     a Win32 EDIT window: auto-language took Voice 003 over the chosen af_heart, 72 characters in 3 pieces, 16.8 s of
     speech made in 2.4 s on the GPU after a 3.9 s load; `stack.py dictate transcribe ... --style verbatim --mode
     live --device cpu` gave the text back word for word except 新芽 as its homophone 心牙, and "Python" inside
     Chinese came back as 派分. Renders of the tray's Features card (the Mandarin row, its Remove confirmation) and of
     the installer's More voices, with every write and setup patched out.
   - Not verified: Download and Remove through the setup worker for real (the packages and files were put in place by
     hand, so the worker's install_zh and the removal ran only in unit tests); the live tray and app (they run the
     installed app's code); Traditional Chinese text; a listener's ear.
   - After merging: rerun install.cmd from the main checkout (it updates the app), then restart voice typing.
40. Thai voices for read aloud (2026-11-08, branch claude/kokoro-thai, on top of item 39). kunato/wayu-kokoro-thai-v1
   at abf63dc (Apache-2.0; training speech distilled from OmniVoice, CC-BY-NC, offered marked at the owner's choice)
   is the voice set `kokoro-th`. Download installs pythainlp 5.4.0, tltk 1.11 and tzdata 2026.6 with --no-deps
   (101 MB, pure Python) into voice typing's environment, checks the Thai front-end loads, then fetches the three ONNX
   graphs, onnx_manifest.json, source_params.npz and styles.npz (326 MB, every sha256 checked) into the HF cache.
   tts.KokoroTh (on a shared OwnFrontEnd base with KokoroZh) runs the graphs with the harmonic source in numpy
   (thai/model.py); the front-end is stacklib/dictation/thai (adapted from the bundle, Apache-2.0). speak.ModelPack
   now describes both Kokoro sets; the zh_* names are wrappers.
   - On this PC (2026-11-08, through dictation.install_th, the worker's own path): the packages are in
     C:\media\dictation\.venv and the model is in D:\huggingface. The machine profile was not changed
     (read_aloud.packs does not name kokoro-th); installed_packs reports kokoro-zh and kokoro-th.
   - Measured through tts.Speech (2026-11-08, 8 pieces, 2 voices): CPU load 2.5 s, 3.2-3.5x real time on 6 threads, working set
     +0.75 GiB; GPU load 2.6-4.0 s, 11-13x real time (0.24-0.36 s a sentence), +1,055 MiB of GPU memory. Before the
     regex cache, tltk took 0.3-1.2 s a sentence (2.3x CPU, 5.5x GPU end to end); after, 30-105 ms.
   - Whisper large-v3-turbo round trip (2026-11-08): 12 voices x 8 plain sentences, 3.1-4.9% character errors (prototype in a
     throwaway python.org 3.14 venv with Smart App Control on); mixed Thai-English sentences and numbers through the
     real engine read right (Whisper writes digits where the front-end says Thai number words, so their CER is not 0).
   - tltk loaded without its dependencies gives the same th2ipa as the full tltk (Python 3.11, scikit-learn 1.2.2,
     numpy<2, pandas 2.2) on 4,004 inputs, before and after the regex cache.
   - Verified: unit tests (tests/test_kokoro_th.py: 31 here, 7 more in voice typing's environment, where the Mandarin
     engine tests and test_read_aloud also pass: 161); `python -m stacklib.dictation speak --list` lists the 12
     voices, and `speak --voice kokoro-th:m_mid_warm --out` read a mixed sentence on the GPU; a render of the
     installer's More voices row and footnote.
   - Not verified: Remove for real (unit tests only); the tray's Features card and its Remove confirmation rendered
     (they use the tested pack_title/pack_note/ModelPack fields); the live tray and app (they run the installed app's
     code); a reading through the speaker button; a Thai listener's ear; text with rare names or Pali/Sanskrit words.
   - After merging: rerun install.cmd from the main checkout (it updates the app), then restart voice typing.

41. Speech models beside Whisper, and the system check (2026-11-09, branch claude/install-system-check-stt-models-176891).
   - Speech models: config/installer.yaml `speech_to_text` lists every model voice typing offers, each with its engine.
     NVIDIA Parakeet TDT 0.6B v3 runs through onnx-asr 0.12.0 on ONNX Runtime, on the CPU by default; NVIDIA
     Canary-Qwen 2.5B through transcribe.cpp 0.4.1 (prebuilt CPU and Vulkan wheel) on the GPU through Vulkan; Whisper
     as before (large-v3 was offered already). Code: stacklib/dictation/stt.py, engine.py (device choice, CPU
     fallback, warm-up), dictation.install_engines (packages and import checks), `python -m stacklib.dictation fetch`,
     `stack.py dictate transcribe --model`. The installer's option and the tray's Settings entry are **Speech model**;
     picking one whose engine is missing starts the setup worker's voice typing step. Voice typing reads **Model
     missing** until the engine is there. SenseVoice Small left out (custom licence; the owner, when asked).
   - On this PC, with the owner's OK (2026-11-09): Parakeet v3 int8 (0.67 GB) and Canary-Qwen Q8_0 (2.8 GB) are in
     D:\huggingface at their pinned revisions, kept for later use. Voice typing's live environment and the machine
     profile were not changed; the throwaway test environment was deleted.
   - Measured on this PC (6 CPU threads; Kokoro recordings of 6.6 to 31.2 s, checked word for word; each heard every
     word but "Ollama"):

     | model | device | load | 7.5 s of speech | 31.2 s | memory |
     |---|---|---|---|---|---|
     | Parakeet v3 int8 | CPU | 3.7 s | 0.31 s (24x) | 1.56 s (20x) | +1.1 GB RAM |
     | Parakeet v3 int8 | CUDA (onnxruntime-gpu 1.31.1) | 4.8 s | 0.41 s (18x) | 1.63 s (19x) | +1.3 GB VRAM |
     | Canary-Qwen Q8_0 | Vulkan | 4.5 s | 0.28 s (27x) | 1.10 s (28x) | +3.3 GB VRAM, +0.2 GB RAM |
     | Canary-Qwen Q8_0 | CPU | 0.8 s | 3.56 s (2.1x) | 15.9 s (2.0x) | mapped file |

     Canary-Qwen's first Vulkan run ever took 20.8 s (shader compilation); in the next process 0.49 s. Through voice
     typing's pipeline (VAD and phrases): 31.2 s in 1.20 s (Parakeet) and 1.28 s (Canary-Qwen). A 94.7 s file through
     Engine.transcribe, as Open WebUI sends it: cut into 5 pieces of 16 to 22 s at pauses; 7.3 s (Parakeet, 3.7 s of it
     loading, 1.5% of words wrong) and 7.8 s (Canary-Qwen, 4.5 s loading, none wrong). A later run gave the same text
     but loaded in 5.8 s and 11.1 s (the files read from D: again).
   - System check: stacklib/syscheck.py. The installer's first page runs it when it opens (card **This PC**, the
     table's **Fit** column, tags in the drop-downs, recommended values for choices the machine file does not set,
     not-recommended features unticked unless installed or ticked by hand); setup's **Check this PC (drives, GPU,
     memory)** step reuses a report under two hours old and warns about chosen values it does not recommend;
     `stack.py check [--no-drives] [--json]`; the tray's Features card adds "recommended here" or "not recommended
     here". Report: .run/install/system-check.json. On this PC the full check took 6 s (C: 3,020 / 1,493 MB/s, D:
     392 / 316 MB/s) and recommended qwen3.5:9b at 32k, Whisper large-v3-turbo, images, and read aloud on the GPU;
     Phoenix not recommended (Smart App Control).
   - Fixed on the way: a context with no measurement was sized from a generic KV figure (the 9B at 64k: 10.4 GB); it is
     now scaled from the model's own measured contexts (6.1 GB). The installer's table had grown past a 1024-pixel
     screen with the new column; the Fit column holds marks only (1,003 px).
   - Verified: unit tests (tests/test_speech_models.py, tests/test_syscheck.py and the installer window tests; the
     numpy ones in a python.org 3.14 venv), the real engines in that venv with Smart App Control on, dictation's
     install_engines checks there, `stack.py check` with the drive test, and renders of the installer's first page
     (dark theme) from this worktree with this PC's status and a fresh PC's.
   - A code review (subagent, read-only) found no must-fix issue, 6 should-fix and 6 to consider; fixed: native engine
     errors now reach the GPU-to-CPU fallback, a failed checksum deletes the cached blob too, broken or older reports
     read as none, Settings also starts the worker when only the model's files are missing, the owner's chat model
     sizes the rest, a working feature's options are tagged but not changed, setup skips its drive test while the
     page's check runs, the tray ignores reports over 30 days old, nvidia-smi fields are asked one by one, Whisper
     small stays usable on a slow processor. Not done: scaling the engine's CPU thresholds (previews, CPU_OK_S) by
     the processor's cores, as the check does; on a 4-core PC Parakeet's previews may cost more than they should.
   - Not verified: a dictation in the live app with the new models (its environment has neither engine yet), the
     Settings switch and the worker's install for real, Open WebUI's microphone with them, Whisper large-v3 (still an
     estimate, not downloaded), Parakeet on CUDA in voice typing's own environment, the page in the light theme and at
     150% scaling, the check on Linux and macOS, an AMD or Intel card.
   - After merging: rerun install.cmd from the main checkout (it updates the app); the installer's first page runs
     the check. To try a model, pick it under Speech model in the tray's Settings tab.

15. Installer (2026-11-01, branch claude/interactive-installer-paths-77aabe): `install.cmd` / `stack.py install` asks for the models
   and Python tools folders, then runs setup in a detached worker (state in `.run/install/state.json`). That day drive D:
   (USB SSD) was not connected, so OLLAMA_MODELS=D:\ollama\models broke every pull. Verified with unit tests, a render
   harness and a stand-in worker; the real worker (registry, Ollama restart, pulls) has not run yet.
