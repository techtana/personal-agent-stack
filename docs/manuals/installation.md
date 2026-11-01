# Installation manual

This guide sets up the stack on one workstation. When you finish, the local models, the gateway and the agent tools
all run on your own machine. Cloud models stay off until you add an Anthropic API key.

The reference machine is SEKAIHOME (Windows 11, RTX 3060 12 GB, 32 GB RAM). Linux and macOS have setup scripts,
but nobody has tested service management on them yet (2026-10-26).

## What you need

| Item | Minimum | Notes |
|---|---|---|
| NVIDIA GPU | 8 GB VRAM | 12 GB runs the default lineup. 8 GB gets the `small-gpu` class. |
| System RAM | 16 GB | 32 GB is needed for the 35B mixture-of-experts model. 16 GB gets a dense 9B model. |
| Disk | ~35 GB free for models | Models can live on another drive (`model_store` in your machine profile). |
| [uv](https://docs.astral.sh/uv/) | 0.12+ | The setup script installs it if it is missing. |
| [Ollama](https://ollama.com/download) | 0.40+ | Install it natively, not in Docker. |
| Claude Code | 2.1.293+ | Use the CLI, the VS Code extension or the desktop app. |
| Node | 24+ | Only needed for the `npx promptfoo` evals. |

You do not need Docker. `infrastructure/docker-compose.yml` is an optional path that nobody has tested.

## Steps

### 1. Install Ollama and Claude Code

Windows:

```powershell
winget install --id Ollama.Ollama --exact
```

```powershell
winget install --id Anthropic.ClaudeCode
```

Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Check that Ollama runs: `ollama --version` prints 0.40 or later.

**Alternative on Windows: a winget configuration file.** `stack.py build` generates `winget/configuration.winget`.
It installs uv, Git, Ollama, PostgreSQL 17, FFmpeg, Tesseract, ExifTool and qpdf in one run, with one UAC prompt.
Most of these are for the planned privacy gate. `winget/configuration.edge.winget` also adds OpenJDK 25 (for
Keycloak) and Caddy, for edge mode. Neither file installs the NVIDIA driver, Python, the uv tools or Claude Code. As
of 2026-10-27 nobody has applied either file end to end on a clean account.

Turn on winget's configuration feature once per machine. Without it, winget reports "Extended features are not enabled":

```powershell
winget configure --enable
```

```powershell
winget configure --file winget\configuration.winget --accept-configuration-agreements
```

### 2. Run setup

From the repository root, on Windows:

```powershell
.\scripts\setup.ps1
```

On Linux, macOS, WSL or Git Bash:

```bash
./scripts/setup.sh
```

Setup does the following, in this order:

1. Installs uv if it is missing (`Installing uv (astral.sh)...`).
2. Detects your hardware and writes `machines/<HOST>.yaml`. `<HOST>` is your computer name.
3. Creates `.env` with new random values for `LITELLM_MASTER_KEY`, `ORCHESTRATOR_BEARER` and `WEBUI_SECRET_KEY`.
   It also adds an empty `ANTHROPIC_API_KEY`. It never overwrites values that are already there.
4. Sets the Ollama user environment variables and restarts the Ollama app if they changed.
5. Installs LiteLLM, Phoenix and Open WebUI as `uv tool`s.
6. Generates the configs (`stack.py build`).
7. Writes `.claude/settings.local.json`, which holds the MCP bearer and the memory directory.
8. Pulls the core models. This can take a long time on a slow disk or a slow connection.

You should see: ``setup complete. Next: `uv run scripts/stack.py up` then `uv run scripts/stack.py smoke`.``

Options: `--no-pull` skips the model downloads, and `--no-restart` leaves Ollama running as it is. On Windows, pass
them like this: `.\scripts\setup.ps1 -Args @('--no-pull')`.

If you don't see the `setup complete` line, see [troubleshooting.md](troubleshooting.md).

### 3. Review your machine profile

Open `machines/<HOST>.yaml`. The `detected:` block is regenerated on refresh. You can change everything else, for example:

- `model_store`: the folder for Ollama models (SEKAIHOME uses `D:\ollama\models`).
- `models.primary`: replace the class default model. SEKAIHOME uses `qwen3.5:9b`.

After you edit it, run:

```powershell
uv run scripts/stack.py build
```

### 4. Start the services

Use the tray app on a desktop. It runs outside any terminal, so the services keep running after you close one:

```powershell
uv run scripts/stack.py tray
```

You should see: `tray: launched; its icon is in the notification area (Windows: under the ^ hidden icons arrow)`.

To start the tray automatically at login:

```powershell
uv run scripts/stack.py tray --install-startup
```

On a server or for a quick test, start the services without the tray:

```powershell
uv run scripts/stack.py up
```

Each service should report `healthy`. Ollama is not started by `up`; the Ollama app runs it.

### Run the services before sign-in (optional)

The tray starts the services only when you sign in. To run them from boot (edge mode), register one Task Scheduler
task per service. Each task runs a supervisor (`stack.py run <service>`) that restarts its service after a crash,
waiting 5 s, then longer each time, up to 60 s.

In an **elevated** (Run as administrator) terminal:

```powershell
uv run scripts/stack.py tasks install
```

The default trigger is `startup`: the tasks run at boot without your password and reach only local resources. If you
cannot use an elevated terminal, register tasks that start when you sign in instead:

```powershell
uv run scripts/stack.py tasks install --trigger logon
```

You should see the tasks in Task Scheduler under the `AgentStack` folder: `phoenix`, `litellm`, `orchestrator`,
`open_webui`. Check them:

```powershell
uv run scripts/stack.py tasks status
```

Each line shows `<service> UP` or `down`, the task's state and its last result.

Things to know:

- A watchdog trigger runs every 2 minutes and restarts a supervisor that died, because Task Scheduler's own restart
  on failure does not.
- To stop a service on purpose, use `uv run scripts/stack.py tasks stop <service>`. It disables the task so the
  watchdog does not bring it back. `uv run scripts/stack.py tasks start <service>` turns it on again.
- `up`, `down` and the tray leave task-run services alone. The tray only shows their status.
- If the tray or `up` already runs a service, its supervisor waits until the port is free instead of starting a second copy.
- Logs go to the same `.run/logs/<service>.log`, in lines starting `[supervisor ...]`.
- As of 2026-10-27 only the `logon` trigger has been tested (on Phoenix). The `startup` trigger has not been run yet.
  Linux gets systemd user units (`agent-stack-<service>.service`), which are untested.

### 5. Check that it works

```powershell
uv run scripts/stack.py smoke
```

You should see `smoke: 8/8 passed`. The first run loads the primary model from disk, which took about 2 minutes on
SEKAIHOME.

### 6. Set up Open WebUI (optional, one time)

1. Open http://127.0.0.1:3000 and create the admin user.
2. Go to **Workspace > Models > Import** and import each file in `config/openwebui/`.
3. Go to **Admin > Integrations > External Tool Servers**. Add an MCP (Streamable HTTP) server at
   `http://127.0.0.1:8765/mcp`, using the `ORCHESTRATOR_BEARER` value from `.env` as the bearer.

### 7. External models

Off. The project is private first: every tier runs on local models, and an API key in `.env` changes nothing.
External models will be explicit, gated choices once the privacy gate is built (`docs/plans/`). Until then the build
refuses `external.enabled: true` in `policy/privacy.yaml`.

### 8. Skills library sync (optional)

`skills/` keeps a copy of the skills you wrote yourself (`~/.claude/skills` and the skills you made in claude.ai), so
they are versioned with the stack. A weekly Claude Code scheduled task copies new and changed skills and opens a pull
request for you to review. The repository is public, so read each pull request before merging it.

1. Check what would be copied:

   ```powershell
   uv run scripts/stack.py skills-sync --dry-run
   ```

   Anthropic's skills, skills marked `license: Proprietary` and names under `exclude` in `skills/sync.yaml` are
   skipped. Add any skill that holds personal data to `exclude`.
2. Make sure `skills-sync` is on `main` (`git log origin/main --oneline -- scripts/stacklib/skills_sync.py` prints a
   commit). The scheduled task runs the command from `main`.
3. In the Claude desktop app, open **Scheduled tasks** and create a new task:
   - Name: `skills-sync`
   - Folder: `C:\Code\personal-agent-stack`
   - Schedule: weekly, Monday 09:00
   - Prompt: everything below the line in [skills/sync-task-prompt.md](../../skills/sync-task-prompt.md)
4. Click **Run now** once. Expect either "no new or modified skills" or a link to a pull request titled
   `feat: sync skills (...)`.
5. Review the pull request and merge it yourself. The task never merges, and it opens no new pull request while one is
   still open.

Scheduled tasks run only while the Claude desktop app is open. A run missed while the app was closed runs at the next
launch. `gh` must be signed in (`gh auth status`) for the task to push and open pull requests.

## Adding another machine

On the new machine, clone the repository and run setup (step 2). It writes that machine's own `machines/<HOST>.yaml`.
To detect the hardware again later, for example after a RAM upgrade:

```powershell
uv run scripts/stack.py doctor --write-profile --refresh
```

## Updating

1. Pull the latest code.
2. Install any changed dependencies:

   ```powershell
   uv sync
   ```

3. Run setup again:

   ```powershell
   .\scripts\setup.ps1 -Args @('--no-pull')
   ```

4. Restart the services from the tray (**Stop all**, then **Start all**), or run `down` and then `up`.

## Removing

1. Remove the login shortcut:

   ```powershell
   uv run scripts/stack.py tray --remove-startup
   ```

2. If you registered scheduled tasks, remove them (elevated terminal for `startup` tasks):

   ```powershell
   uv run scripts/stack.py tasks remove
   ```

3. In the tray menu, choose **Stop services and quit**.
4. Remove the tools: `uv tool uninstall litellm`, `uv tool uninstall arize-phoenix`, `uv tool uninstall open-webui`.
5. Delete `.run/` (logs, pid files, Phoenix data) and the models in your `model_store` folder.
