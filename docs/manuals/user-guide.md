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

- **Show status**: opens the status window (a left-click does the same).
- One line for each service: `● up` or `○ down`.
- **Open chat (Open WebUI)**, **Open traces (Phoenix)**, **Open gateway admin (LiteLLM)**: open each one in your browser.
- **Start all services**, **Stop all services**.
- **Open logs folder**: opens `.run/logs`.
- **Start at login**: turns the login shortcut on or off.
- **Quit (keep services running)**: closes only the tray.
- **Stop services and quit**: stops the services, then closes the tray.

**Status window**

The window shows `N/M running, checked HH:MM:SS` and one row for each service. Each row has its state (`running` or
`stopped`), an **Open** button for the web UIs and a **Start**/**Stop** button. Ollama has no Start/Stop button
because the Ollama app runs it. At the bottom are **Open chat**, **Start all**, **Stop all**, **Logs** and
**Start at login**. Closing the window only hides it.

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
- Open WebUI: pick a department from the model list.

## Changing an agent or a model

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

Traces are written to `traces/litellm/` (gateway) and `traces/claude/` (Claude Code hooks), and they also appear in Phoenix.
