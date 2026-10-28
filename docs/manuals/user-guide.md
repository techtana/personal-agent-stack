# User manual

This guide covers everyday use: checking that the stack is running, working with the department agents and reading
what happened. To set the stack up, see [installation.md](installation.md).

## The tray app

The tray app keeps the services running and shows whether they are up. On Windows its icon is in the notification
area, under the **^** hidden-icons arrow.

**Icon colour**

| Colour | Meaning |
|---|---|
| Green | Every service is up. |
| Amber | One of Phoenix, the orchestrator or Open WebUI is down. |
| Red | The LiteLLM gateway or Ollama is down, so the agents cannot reach a model. |
| Grey | The tray is starting or busy. |

Hover over the icon to see `Agent Stack: N/M up`. The tray checks the services every 10 seconds.

**Menu** (right-click the icon)

- **Show status**: opens the status window on the Overview tab (a left-click does the same).
- **Usage by model**, **Settings**: open the window on that tab.
- One line for each service: `● up` or `○ down`.
- **Open chat (Open WebUI)**, **Open traces (Phoenix)**, **Open gateway admin (LiteLLM)**: open each one in your browser.
- **Start all services**, **Stop all services**.
- **Open logs folder**: opens `.run/logs`.
- **Start at login**: turns the login shortcut on or off.
- **Quit (keep services running)**: closes only the tray.
- **Stop services and quit**: stops the services, then closes the tray.

**Status window** (since 2026-10-27)

The window is titled **Agent Stack** and follows Windows light or dark mode. The header shows the machine name, the
primary model and its context size, and `cloud tiers on` or `local only`. The pill on the right shows
`N/M running · checked HH:MM:SS`. Closing the window only hides it. It has three tabs.

*Overview*

- **Services**: one row per service with its role, port and state: `Running (pid N)`, `Stopped`, or
  `Off in settings` (turned off in the Settings tab). Open WebUI, Phoenix and LiteLLM have an **Open** button. Every
  service except Ollama has **Start**/**Stop**; the Ollama app runs Ollama.
- **Loaded in Ollama**: each loaded model with **Size**, **On GPU** (share of the model in VRAM), **Context** and
  **Unloads** (when Ollama will drop it). "No model is loaded" is normal: the first request loads one.
- At the bottom: **Open chat**, **Start all**, **Stop all**, **Logs** and the **Start at login** checkbox.

*Usage*

Counts every request that went through the gateway, read from `traces/litellm/<date>.jsonl`.

- **Period**: **Today**, **7 days** (default) or **30 days**.
- **Group by**: **Gateway alias** (the name the client asked for, such as `local-primary` or `docs`) or
  **Served model** (the model that answered, such as `qwen3.5:9b`).
- Tiles: **Requests**, **Input tokens**, **Output tokens**, **Errors** (red when above 0) and **API cost**. Local
  models cost $0; cost is cloud API spend.
- The table has **Model**, **Requests**, **Errors**, **Input tok**, **Output tok**, **Avg latency**, **Output tok/s**,
  **Cost** and **Last used**. Click a heading to sort. A red row means every request in it failed.
- The chart shows tokens per day. Select a table row to show only that model.

If the table says "No gateway requests in this period", either nothing used the gateway in that period or
**Write usage traces** is off in Settings.

*Settings*

Changes the most common values in your machine profile, `machines/<HOST>.yaml`, without editing the file.

| Group | Setting | What it does |
|---|---|---|
| Models | **Primary model**, **Primary context (tokens)** | The model behind `local-primary` and every `<department>-local`, and its context size. |
| Models | **Memory-map primary weights** | Needed for the 35B MoE model; leave off for dense models. |
| Models | **Small model**, **Small context (tokens)** | The model behind `local-small`. Keep the context equal to the primary's when both use the same model. |
| Tracing and services | **Write usage traces** | Writes `traces/litellm/`. The Usage tab and `retro` need it. |
| Tracing and services | **Phoenix tracing** | Runs Phoenix. Leave off on SEKAIHOME: Smart App Control blocks it. |
| Tracing and services | **Open WebUI (chat)** | Runs the chat at http://127.0.0.1:3000. |
| Ollama runtime | **Keep models loaded for**, **KV cache precision**, **Flash attention**, **Parallel requests per model** | Ollama's memory and speed options. |

A changed row is marked **changed**. The bar at the bottom says what **Apply** will do. **Apply** saves the changed
lines (comments are kept), rebuilds the configs and restarts only what the change needs. Changing an Ollama runtime
option asks **Restart Ollama?** first, because requests in progress will fail. **Revert** discards unsaved changes;
**Open profile file** opens the YAML.

Cloud tiers are shown but cannot be changed here. Turning them on is a deliberate `.env` decision.

## What normal looks like

- `uv run scripts/stack.py status` lists each service as `UP`.
- `uv run scripts/stack.py smoke` prints `smoke: 8/8 passed`.
- A reply from the 9B model starts within a few seconds once the model is loaded. The first request after a long idle
  period reloads the model, which takes about 2 minutes from the USB drive on SEKAIHOME.

| Service | Address | What it is for |
|---|---|---|
| Ollama | http://127.0.0.1:11434 | Runs the local models on the GPU. |
| LiteLLM gateway | http://127.0.0.1:4000 (admin UI at `/ui`) | Sends each request to a local or cloud model. |
| Phoenix | http://127.0.0.1:6006 | Shows a trace of every request. |
| Orchestrator MCP | http://127.0.0.1:8765/mcp | Lets agents hand tasks to departments. |
| Open WebUI | http://127.0.0.1:3000 | A chat interface. |

## Working with the departments

There are six department agents: `app-dev`, `testing`, `security`, `devops`, `code-review` and `docs`.

**In Claude Code (your subscription)**

- Open this repository in Claude Code. The departments appear as subagents. Mention one by name: `@security review src/auth.py`.
- Run one department as the main agent: `claude --agent docs`.
- Skills: `/retro`, `/harden`, `/brainstorm`, `/why-routed`.
- The orchestrator MCP server provides `delegate(department, task, tier)`, `get_job`, `cancel_job`, `list_departments` and
  `record_lesson`. Approve the server the first time Claude Code asks.

**In Claude Code on local models (profile B)**

```powershell
.\scripts\claude-local.ps1
```

This runs Claude Code against the gateway and uses a separate config folder (`~/.claude-local`), so it uses none of
your plan quota. Nobody has tried a full live session this way yet (2026-10-26).

**Other tools**

- OpenCode: `opencode.json` sets up the gateway as provider `litellm`.
- VS Code autocomplete: `config/continue/config.yaml` (Continue).
- Open WebUI: pick a department or model from the model list at the top of the chat, or type `@` in the input box
  to pick one for a single message. Writing "use Claude" in a message does not switch models: the message goes to the
  model you picked, and `local-primary` always answers locally. Only models the gateway offers appear in the list.

## Changing an agent or a model

To change the primary or small model, a context size, tracing or an Ollama option, use the tray's **Settings** tab.
For anything else:

1. Edit `agents/<id>.yaml`, `agents/_common.md` or `machines/<HOST>.yaml`. Never edit the generated files.
2. Regenerate the configs:

   ```powershell
   uv run scripts/stack.py build
   ```

3. Restart the gateway: in the tray, click **Stop** and then **Start** on the LiteLLM row.

## Seeing what happened

```powershell
uv run scripts/stack.py why-routed --last 20
```

This shows which model handled each recent request, and why.

```powershell
uv run scripts/stack.py retro -- --days 7
```

This writes a weekly report on cost and outcomes for each department. Then run `/retro` in Claude Code to propose
changes. A person reviews every change, and nothing merges on its own.

```powershell
uv run scripts/stack.py bench
```

This measures the primary model's speed in tokens per second. Compare the result with the benchmark table in
`memory/state.md`.

Traces are written to `traces/litellm/` (gateway) and `traces/claude/` (Claude Code hooks). The tray's **Usage** tab
summarises the gateway traces. They also appear in Phoenix when Phoenix runs.
