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
| `no machine profile at ...` | This computer has no `machines/<HOST>.yaml`. | Run `uv run scripts/stack.py doctor --write-profile`. |
| `<svc>: something already answers on its port; not starting a second copy` | Another copy or another program is using the port. | Use the copy that is already running, or stop the other program. |
| `WARN <svc>: pid N now belongs to another process ...; leaving it alone` | A pid file is out of date (Windows reuses pids). | Nothing to do. The stack does not stop the other process. Start the service again if you need it. |
| Services stop when you close a terminal or a Claude Code session | They were started from that session. | Start them with the tray app (`stack.py tray`) instead of `up`. |
| Services are down after you sign in | Start at login is off, or the tray failed. | Run `uv run scripts/stack.py tray --status`, then look in `.run/logs/tray.log`. |
| `tray: already running` but you see no icon | The icon is under the hidden-icons arrow. | Click **^** in the taskbar. |
| `[tray] another tray instance is running; exiting` in the log | A second tray was started. | Nothing to do. One tray is enough. |
| A model load fails with HTTP 500 after about 5 minutes | Ollama copies the MoE experts into RAM and runs out of memory or time. | Keep `use_mmap: true` for the 35B model and `OLLAMA_LOAD_TIMEOUT=15m` (both in `machines/_defaults.yaml`). Close large apps, or use the 9B primary. |
| The first reply takes minutes | A cold model load from a slow (USB) disk. | This is expected. It took 2 min 10 s for the 9B on SEKAIHOME. |
| Ollama reloads the model when you switch departments or tiers | Two tiers use the same model with different `num_ctx` or load options. | Give them the same `num_ctx` and options in `machines/<HOST>.yaml`, then rebuild. |
| Replies are much slower than the benchmark in `memory/state.md` | RAM pressure, or MoE experts placed on the CPU. | Close desktop apps. For the MoE model, try `LLAMA_ARG_N_CPU_MOE=<n>` under `ollama_env` in `machines/<HOST>.yaml`, then rerun setup. |
| The gateway returns 401 | The client sent the wrong key. | Send `LITELLM_MASTER_KEY` from `.env` as a Bearer token. |
| The cloud tier is never used | On `main`: `ANTHROPIC_API_KEY` is empty, so the build sent every tier to a local model. With a build that includes PR #8: external models are off in `policy/privacy.yaml`, whatever `.env` holds. | On `main`, add the key, run `stack.py build` and restart LiteLLM (read installation step 7 first). With PR #8, this is by design until the privacy gate exists. |
| You asked the chat to "use Claude", and the local model replied that it cannot | The message went to the model picked in Open WebUI's model list. A model cannot switch to another model, and `local-primary` is always local. | Pick another model in the list, or with `@` in the input box. Claude models appear there only once the gateway offers them (see the row above). Claude cannot generate images either way. |
| Phoenix shows `Stopped`, or `WARN phoenix: ...` in the log | Since 2026-10-26 Smart App Control blocks compiled modules in Phoenix's tool environment (pyarrow, sqlalchemy, pandas). | Turn **Phoenix tracing** off in the tray's Settings tab. The Usage tab reads the JSONL traces and does not need Phoenix. The plans remove Phoenix. |
| The LiteLLM admin UI (`/ui`) shows "Not connected to DB!" | The admin UI needs Postgres, which is not set up. | Use the tray's Usage tab or `stack.py why-routed` instead. |
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
