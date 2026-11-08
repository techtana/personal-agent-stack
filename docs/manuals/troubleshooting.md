# Troubleshooting

Find what you see in the first column, then follow the fix.

## Health checks

Run these first:

```powershell
uv run scripts/stack.py status
```

```powershell
uv run scripts/stack.py doctor
```

```powershell
uv run scripts/stack.py smoke
```

If you registered scheduled tasks:

```powershell
uv run scripts/stack.py tasks status
```

Each service also answers a health URL on 127.0.0.1: Ollama at `:11434/api/version`, LiteLLM at
`:4000/health/liveliness`, the orchestrator at `:8765/healthz`, Open WebUI at `:3000/health` and Phoenix at `:6006/`.

Logs:
- Each service: `.run/logs/<service>.log`.
- The tray app: `.run/logs/tray.log`.
- Ollama on Windows: `%LOCALAPPDATA%\Ollama\server.log`.

## Symptoms

| What you see | Likely cause | Fix |
|---|---|---|
| Tray icon is red | The gateway or Ollama is down. | Open the status window and click **Start** on LiteLLM. If Ollama is down, start the Ollama app from the Start menu. |
| `WARN <svc>: Windows refused to start ...` (often WinError 4551) | Smart App Control blocked a program. | The stack starts tools through each tool environment's `python.exe`, which Smart App Control allows. If it blocks that too, the remaining options are turning Smart App Control off (your security decision) or running the tools with `uv tool run`. |
| `WARN <svc>: executable not found ...` | The uv tools are not installed. | Run `uv run scripts/stack.py setup --no-pull`. |
| `Error: 400 Bad Request: mkdir D:\ollama: The system cannot find the path specified` while pulling | The models folder (`OLLAMA_MODELS`) is on a drive that is not connected, for example an unplugged USB SSD. | Reconnect the drive, or run the installer (`install.cmd` or `uv run scripts/stack.py install`) and choose another models folder; it updates the profile and Ollama's environment and restarts Ollama. |
| `path guard: agent_access.allowed_roots is empty` or `... is outside agent_access.allowed_roots` | A `media:` folder in `machines/<HOST>.yaml` is not in the allowed list. | Add the folder you chose to `agent_access.allowed_roots`, or choose the media folder in the installer, which adds it. |
| ComfyUI stops at start-up with `ImportError: DLL load failed ... An Application Control policy has blocked this file` | Smart App Control refused a compiled module in ComfyUI's environment (PyAV 19.0.2 was refused on 2026-11-04). | Look up the file in Event Viewer (CodeIntegrity, event 3033). For PyAV, run `media install` again, which pins `av==17.0.0`. For another package, try an older version in the same way and add it to `SAC_PINS` in `scripts/stacklib/media.py`. |
| The image button is missing in Open WebUI | Image generation is off in Open WebUI's settings, or ComfyUI is off. | Run `uv run scripts/stack.py media provision`, reload the page, and check that ComfyUI is **Running** in the tray. |
| An image takes minutes, or ComfyUI's log shows out-of-memory | The chat model holds the GPU. | Click **Media** in the tray's GPU card, then try again; click **Chat** afterwards. |
| Voice typing: the bubble says **Hotkey not available** | Another program registered the same key (the Claude desktop app has Ctrl+Alt+Space). | Pick another **Voice typing hotkey** in the tray's Settings tab; Apply restarts voice typing. The button works meanwhile. |
| Voice typing: **The microphone sends silence** | The microphone is muted, or Windows blocks desktop apps from it. | Settings > Privacy & security > Microphone: turn on **Let desktop apps access your microphone**, and unmute the device. |
| Voice typing: **Microphone not available** | No input device, or `dictation.mic` names one that is not connected. | Connect a microphone or clear `dictation.mic`. `uv run scripts/stack.py dictate check` lists the microphones it can see. |
| Voice typing: **Copied to the clipboard** instead of typed | You switched windows while it worked, or the window runs as administrator. | Press Ctrl+V where the text should go. |
| Voice typing: **Cleanup skipped: gateway not reachable** | LiteLLM is down. | Start LiteLLM in the tray. Until then you get the transcript with only the filler sounds removed. |
| Voice typing: **GPU not used ... Running small on the CPU** | cuBLAS 12 was not found, or the card had no room. | `stack.py dictate check` shows `cublas_dir` (Ollama ships it in `lib\ollama\cuda_v12`). Free VRAM with **Chat** in the tray's GPU card, then stop and start voice typing. |
| Voice typing row: **program not found** | Its environment is not installed. | Run `uv run scripts/stack.py dictate install`. |
| Refine: **Nothing selected** | The app did not copy anything: no text was selected, or the app ignores Ctrl+C there. | Select the text again and retry. In Logseq select text inside the block you are editing. |
| Refine: **Copied to the clipboard** instead of replaced | You clicked elsewhere or switched windows while the model worked, so the selection was no longer the same. | Select the old text and press Ctrl+V; the new text is also in **Refine history**. |
| Refine: **Kept your text** | The model's reply read like an answer, or grew or shrank far more than the style allows. | Try another style, or copy the suggestion from **Refine history** if it is fine after all. |
| Refine: **Could not refine the text: the gateway is not reachable** | LiteLLM is down. | Start LiteLLM in the tray; nothing was replaced. |
| Refine: **The selection includes a picture or a table** | Pasting plain text would delete them. | Select only the text around them. |
| Refine: Ctrl+Alt+R no longer types (R) in Word | The refine hotkey has it while voice typing runs. | Pick another **Refine hotkey** in the tray's Settings tab. |
| `no machine profile at ...` | This computer has no `machines/<HOST>.yaml`. Profiles are local since 2026-11-07, so a pull that removed the old tracked copy also removed yours unless you kept a backup. | Copy your backup back into `machines\`, or run `install.cmd` (or `uv run scripts/stack.py doctor --write-profile`). To get the last committed copy: `git restore --source <commit>^ --worktree machines/<HOST>.yaml`, where `<commit>` is the one `git log --diff-filter=D -1 --format=%h -- machines/<HOST>.yaml` prints. |
| `<svc>: something already answers on its port; not starting a second copy` | Another copy or another program is using the port. | Use the copy that is already running, or stop the other program. |
| `WARN <svc>: pid N now belongs to another process ...; leaving it alone` | A pid file is out of date (Windows reuses pids). | Nothing to do. The stack does not stop the other process. Start the service again if you need it. |
| Services stop when you close a terminal or a Claude Code session | They were started from that session. | Start them with the tray app (`stack.py tray`) instead of `up`. |
| Services are down after you sign in | Start at login is off, or the tray failed. | Run `uv run scripts/stack.py tray --status`, then look in `.run/logs/tray.log`. |
| `tray: already running` but you see no icon | The icon is under the hidden-icons arrow. | Click **^** in the taskbar. |
| `[tray] another tray instance is running; exiting` in the log | A second tray was started. | Nothing to do. One tray is enough. |
| A model load fails with HTTP 500 after about 5 minutes | Ollama copies the MoE experts into RAM and runs out of memory or time. | Keep `use_mmap: true` for the 35B model and `OLLAMA_LOAD_TIMEOUT=15m` (both in `machines/_defaults.yaml`). Close large apps, or use the 9B primary. |
| The first reply takes minutes | A cold model load from a slow (USB) disk. | Run `uv run scripts/stack.py disks`. Under 100 MB/s, fix the drive's connection ([choosing-drives.md](choosing-drives.md#fix-a-usb-drive-that-reads-at-about-40-mbs)). The 9B's 2 min 10 s loads on the reference machine matched a USB 2.0 link. |
| **Check drive speed** shows `!` and `reads at only 41 MB/s ... That is USB 2.0 speed` | A USB SSD is connected at USB 2.0 speed: a worn USB-C contact, a front or USB 2 port, or a charge-only cable. | Turn the USB-C plug over, use a USB 3 port on the back and the drive's own cable, then run `stack.py disks` again. |
| **Check drive speed** says `The Python tools are on D:, a USB drive` | `UV_TOOL_DIR` is on a removable drive. | Run the installer again and choose a folder on the internal drive for the Python tools. |
| **Install OpenClaw** fails with `Node.js is ... after winget` | The Node.js upgrade was declined or failed. | Install Node.js 26 LTS from https://nodejs.org or `winget install --id OpenJS.NodeJS.LTS`, then run setup again. |
| The tray's OpenClaw row is red (**Uses an outside model**) or amber | OpenClaw was onboarded with a cloud provider or Ollama, or not onboarded yet. | Click **Use gateway** in the tray, or run `uv run scripts/stack.py openclaw`. OpenClaw keeps the old config as `~/.openclaw/openclaw.json.bak`. |
| **Use gateway** says `LITELLM_MASTER_KEY is not in .env` | Setup has not created the stack's secrets yet. | Run `uv run scripts/stack.py setup --no-pull`, then click it again. |
| The tray's Hugging Face row says **Drive missing** | `HF_HOME` is on a USB drive that is unplugged. | Plug the drive in. The row turns green within a minute. |
| Hugging Face prints a warning about symlinks, or the cache uses more space than expected | The cache drive is exFAT, which has no symbolic links. | Nothing breaks. To avoid it, format a drive you use only with this PC as NTFS (this erases it). |
| Ollama reloads the model when you switch departments or tiers | Two tiers use the same model with different `num_ctx` or load options. | Give them the same `num_ctx` and options in `machines/<HOST>.yaml`, then rebuild. |
| Replies are much slower than the benchmark in `memory/state.md` | RAM pressure, or MoE experts placed on the CPU. | Close desktop apps. For the MoE model, try `LLAMA_ARG_N_CPU_MOE=<n>` under `ollama_env` in `machines/<HOST>.yaml`, then rerun setup. |
| The gateway returns 401 | The client sent the wrong key. | Send `LITELLM_MASTER_KEY` from `.env` as a Bearer token. |
| Open WebUI shows "Failed to connect to MCP server" above a reply; the orchestrator log shows `401` / `invalid_token` | The tool server was saved with another `.env` value (for example `WEBUI_SECRET_KEY`). | In **Admin > Settings > Integrations > External Tool Servers**, edit the connection and paste `ORCHESTRATOR_BEARER`. |
| The cloud tier is never used | By design since 2026-10-26: every tier is private and local. | Nothing to fix. External models will be explicit aliases behind the privacy gate (`docs/plans/`). |
| You asked the chat to "use Claude", and the local model replied that it cannot | The message went to the model picked in Open WebUI's model list. A model cannot switch to another model, and `local-primary` is always local. | Pick another model in the list, or with `@` in the input box. Claude models do not appear there while external models are off (see the cloud-tier row above). Claude cannot generate images either way. |
| Phoenix shows `Stopped`, or `WARN phoenix: ...` in the log | Since 2026-10-26 Smart App Control blocks compiled modules in Phoenix's tool environment (pyarrow, sqlalchemy, pandas). | Turn **Phoenix tracing** off in the tray's Settings tab. The Usage tab reads the JSONL traces and does not need Phoenix. The plans remove Phoenix. |
| The LiteLLM admin UI (`/ui`) shows "Not connected to DB!" | The admin UI needs Postgres, which is not set up. | Use the tray's Usage tab or `stack.py why-routed` instead. |
| The `skills-sync` task reports "skills-sync not on main yet" | The sync tool is on a branch that is not merged. | Merge it into `main`, then click **Run now** on the task. |
| The `skills-sync` task reports an open sync pull request and stops | A previous sync pull request is waiting for review. | Merge or close it; the next run picks up anything newer. |
| The `skills-sync` task did not run on Monday | The Claude desktop app was closed. | It runs at the next app launch, or click **Run now**. |
| A skill you expected is `skipped` or missing | It is Anthropic's, marked proprietary, listed under `exclude`, or held back for personal data. | Check `skills/sync.yaml` and the task's last report. |
| Usage tab says "No gateway requests in this period" | Nothing used the gateway in that period, or **Write usage traces** is off. | Pick a longer period, or turn **Write usage traces** on in Settings and click **Apply**. |
| Settings **Apply** says `LiteLLM runs under a scheduled task` or `LiteLLM was started outside this stack` | The tray restarts only a LiteLLM it started itself. | Run `uv run scripts/stack.py tasks stop litellm`, then `tasks start litellm`; or restart that LiteLLM yourself. |
| Settings **Apply** says `LiteLLM did not come back within 2 minutes` | The new config failed to load. | Read `.run/logs/litellm.log`, fix the setting, then **Apply** again. |
| `up` or `down` says `<svc>: supervised by a scheduled task` | That service runs under a Task Scheduler task. | Use `uv run scripts/stack.py tasks start <svc>` or `tasks stop <svc>`. |
| `tasks install` prints `schtasks refused: ...` | `startup` tasks need an elevated terminal to register. | Run it again as administrator, or use `--trigger logon`. |
| A service you stopped comes back about 2 minutes later | Its task is still enabled, so the watchdog trigger restarted it. | Stop it with `uv run scripts/stack.py tasks stop <svc>`, which disables the task. |
| `winget configure` says "Extended features are not enabled" | winget's configuration feature is off. | Run `winget configure --enable` once. |
| The Anthropic API returns 400 about `temperature` | Claude models no longer accept `temperature`, `top_p` or `top_k` (since 2026-10-21). | Set these only under `local:` in `agents/<id>.yaml`. |
| Claude Code does not show the orchestrator, or shows `ECONNREFUSED` | The server is not approved, or it is not running. | Approve the `.mcp.json` server when Claude Code asks. Check that the orchestrator is up in the tray, then restart Claude Code. |
| Orchestrator calls fail with 401 | The bearer is empty or does not match. | Make sure the variable is named `ORCHESTRATOR_BEARER`. Claude Code blanks variables named `*_TOKEN` or `*_API_KEY` in `.mcp.json`. Rerun setup to write `.claude/settings.local.json`. |
| `WARNING: ORCHESTRATOR_BEARER is empty` in the orchestrator log | `.env` has no bearer. | Rerun setup, which generates a bearer. Until then the server listens only on 127.0.0.1, with no authentication. |
| `FileNotFoundError: ... not found; run uv sync first` when the tray starts | The project's `.venv` is missing. | Run `uv sync`. |
