# Installation manual

This guide sets up the stack on one workstation. When you finish, the local models, the gateway and the agent tools
all run on your own machine. Cloud models stay off until you add an Anthropic API key.

The reference machine runs Windows 11 with an RTX 3060 12 GB and 32 GB of RAM. Linux and macOS have setup scripts,
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

On Windows, double-click `install.cmd` in the repository root, or run `.\scripts\setup.ps1`. On Linux, macOS, WSL
or Git Bash, run `./scripts/setup.sh`.

The installer has two pages, in a window (or the same questions in the terminal when there is no display, or with
`--no-gui`).

**Page 1: Which features do you want?** One row per feature. Two are required and always installed; the others are
your choice:

| Feature | Required | What you get |
|---|---|---|
| Local models (Ollama) | yes | Ollama and the chat model every other feature talks to. |
| Gateway and agent tools | yes | LiteLLM with the privacy rules, the orchestrator for the departments, and the tray app. |
| Chat in the browser (Open WebUI) | no | Chat at http://127.0.0.1:3000, with documents, the agents' tools and the image button. |
| Trace viewer (Phoenix) | no | Each request's steps, for debugging. The tray's Usage tab works without it. |
| Image generation (ComfyUI) | no | ComfyUI with Z-Image-Turbo for the chat's image button. Needs the media folder. |
| Voice typing (Whisper) | no | A hotkey and a mic button that type what you say into any app ([details](user-guide.md#voice-typing)). |
| Recordings in Claude Desktop (Whisper) | no | A local Whisper server that Claude Desktop uses to transcribe audio files. Needs the media folder. |
| OpenClaw | no | An agent app set up to use only the gateway ([details](choosing-drives.md#openclaw)). |

Each row shows what that feature takes on this PC: **Disk GB**, **GPU memory GB** (held while loaded; a range such as
`0.4 to 10.5` means idle and while working), **GPU work** (how long the GPU is busy, such as `~11 s per image`), **CPU
while busy** (logical processors, such as `~1 of 12`) and **RAM GB**. Point at a row, or tab to its checkbox, and the
box under the table explains it: when the memory is held, what keeps the GPU busy, and where each figure comes from.
Figures marked *measured* come from the reference PC (an RTX 3060 12 GB, a Ryzen 5 5500, 32 GB of DDR4); the chat
model's GPU memory is read from Ollama when the model is loaded; the rest are estimates and say so.

The box **Your choice on this PC** adds up what you ticked and says what does not fit, for example:

- how much setup downloads (installed features count nothing; the Whisper model that voice typing and recordings
  share counts once);
- the GPU memory with everything loaded at once, against what the card has free after Windows;
- whether an image job fits next to the chat model, or needs **Media** on the tray's GPU card first;
- the system memory the stack takes, idle and after an image job, against the RAM in this PC;
- the CPU, and a warning when there is no NVIDIA GPU or Smart App Control may block Phoenix.

Features that are installed and turned on are ticked and cannot be unticked: the installer only adds features. To turn
one off, use **Settings** in the tray (Open WebUI, Phoenix, ComfyUI, voice typing). A feature that is installed but
off is unticked; ticking it turns it back on. A feature your profile turns on whose program or model is missing is
ticked, so setup repairs it. When a check fails (`Not checked`, for example because `uv` did not answer), the installer
leaves that feature exactly as it is. To add features later, run the installer again (`install.cmd`, or
**Add features...** in the tray); it starts on this page with what you have.

`uv run scripts/stack.py features` prints the same table, each feature's status and the total for what is installed
(`--details` adds the explanations).

**Page 2: Where should Agent Stack put its files?**

- **Models folder**: where Ollama keeps downloaded models (`OLLAMA_MODELS`). Needs about 8 GB for the core models.
  If the folder in your machine profile is on a drive that is not connected, the installer says so and offers
  Ollama's default, `%USERPROFILE%\.ollama\models`. If models already exist in the old folder, it offers to move them.
- **Python tools folder**: where uv puts LiteLLM and, when chosen, Open WebUI and Phoenix (`UV_TOOL_DIR`, 0.6 GB for
  LiteLLM, 1.9 GB for Open WebUI, 0.5 GB for Phoenix). Keep the path short; deep Python packages break past Windows'
  260-character limit.
- **Media folder**, only when you chose images or recordings: ComfyUI, Whisper and their models (about 17 GB for
  images, 4 GB for recordings). Agent sessions and media tools may use only this folder.

Which drive to pick for each: [choosing-drives.md](choosing-drives.md). In short, models and the Hugging Face cache
can go on a second or USB drive that reads at 200 MB/s or more; the Python tools stay on the internal drive.

Under **Options** you can also choose to download the models now, check each drive's speed and put the Hugging Face
cache next to the models (all on by default). When models already sit in another folder, it offers to move them.

Under each folder it shows the free space on that drive and what the chosen features need there; **Install** stays
disabled until every folder is usable. **Back** returns to the features with your ticks kept. **Install** writes the
models folder (`model_store` and `ollama_env.OLLAMA_MODELS`) and the chosen features (`services.open_webui`,
`services.comfyui`, `services.dictation`, `observability.phoenix`, and `media.root` when needed) into
`machines/<HOST>.yaml`, keeping your comments, then starts setup as a background process. You can close the window:
setup keeps going, and opening the installer again (or `uv run scripts/stack.py install --status`) shows each step's
progress. The log is `.run/install/install.log`.

Setup does the following, in this order:

1. Installs uv if it is missing (`Installing uv (astral.sh)...`).
2. Detects your hardware and writes `machines/<HOST>.yaml`. `<HOST>` is your computer name. The file stays on this
   computer: git ignores it, so your computer name and folders never reach the public repository.
3. Creates `.env` with new random values for `LITELLM_MASTER_KEY`, `ORCHESTRATOR_BEARER` and `WEBUI_SECRET_KEY`.
   It also adds an empty `ANTHROPIC_API_KEY`. It never overwrites values that are already there.
   Then **Check drive speed** measures every local drive and warns about slow ones; a warning shows as an amber **!**
   and does not stop setup ([choosing-drives.md](choosing-drives.md#check-a-drives-speed)).
4. Sets the Ollama user environment variables and restarts the Ollama app if they changed.
5. Installs LiteLLM, and Open WebUI and Phoenix when chosen, as `uv tool`s.
6. Generates the configs (`stack.py build`).
7. Writes `.claude/settings.local.json`, which holds the MCP bearer and the memory directory.
8. Pulls the core models. This can take a long time on a slow disk or a slow connection.
9. **Set up the Hugging Face cache**: sets `HF_HOME` to `<models drive>:\huggingface`, moves an existing cache there,
   keeps the token on the internal drive, and installs the `hf` command
   ([details](choosing-drives.md#hugging-face-cache)).
10. **Install OpenClaw**: upgrades Node.js with winget if it is older than OpenClaw needs (Windows asks for
    administrator approval), runs `npm install -g openclaw@latest`, then sets OpenClaw up with the gateway as its only
    model provider ([details](choosing-drives.md#openclaw)).
11. **Install voice typing (Whisper)**: only when voice typing is chosen (`services.dictation: native`); it builds
    its environment under the media folder and fetches the Whisper model. Without the installer:
    `uv run scripts/stack.py dictate install` ([details](user-guide.md#voice-typing)).
12. **Install recordings for Claude Desktop (Whisper)**: only when chosen; it builds Whisper's environment under the
    media folder, fetches the model (shared with voice typing) and registers the server `local-whisper` in Claude
    Desktop's config, after a backup. Quit Claude Desktop from its tray icon and reopen it to load the server. An
    entry Claude Desktop already has is left as it is, and an installer run from a git worktree adds none (the server
    would count its usage in the worktree); `uv run scripts/stack.py whisper install` from the main checkout updates
    or adds it on purpose.

The images step (ComfyUI) runs only when images are chosen, and OpenClaw's only when OpenClaw is.

A failed step does not stop the others; the window marks it with a cross and Ollama's or uv's message, and
**Change choices and run again** goes back to the features page. Steps that already ran are quick the second time.

Unattended setup (no questions; uses the folders already in the profile): `uv run scripts/stack.py setup`, or on
Windows `.\scripts\setup.ps1 -Args @('--no-pull')`. `--no-pull` skips the model downloads and `--no-restart` leaves
Ollama running as it is. It ends with ``setup complete. Next: `uv run scripts/stack.py up` then `uv run scripts/stack.py smoke`.``
and stops with an error when the models folder is on a drive that is not connected.

If setup reports problems, see [troubleshooting.md](troubleshooting.md).

### 3. Review your machine profile

Open `machines/<HOST>.yaml`. The `detected:` block is regenerated on refresh. You can change everything else, for example:

- `model_store`: the folder for Ollama models; the installer sets it (and `ollama_env.OLLAMA_MODELS`) for you.
- `models.primary`: replace the class default model. The reference machine uses `qwen3.5:9b`.

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
the reference machine.

### 6. Set up Open WebUI (optional, one time)

1. Open http://127.0.0.1:3000 and create the admin user.
2. Go to **Workspace > Models > Import** and import each file in `config/openwebui/`.
3. Go to **Admin > Integrations > External Tool Servers**. Add an MCP (Streamable HTTP) server at
   `http://127.0.0.1:8765/mcp`, using the `ORCHESTRATOR_BEARER` value from `.env` as the bearer, and give it the
   ID `personal-agent-stack`. The imported department models name that ID, so the orchestrator tools are switched
   on in every new chat with them (you can still switch them off per chat under **Tools**). Other models, such as
   the plain `local-primary`, start with the tools off.

### 6b. Images (optional)

Tick **Image generation (ComfyUI)** on the installer's features page (about 17 GB: ComfyUI, PyTorch with CUDA and
Z-Image-Turbo); page 2 then asks for the **Media** folder. The folder is written to `machines/<HOST>.yaml` as
`media.root` and added to `agent_access.allowed_roots`, the list of folders media tools and agent sessions may use.
Setup then:

- clones ComfyUI into `<media.root>\comfyui` and builds its Python environment from the python.org Python (its
  signed launchers pass Smart App Control), with the uv download cache in `<media.root>\.uv-cache`;
- downloads the model files listed in `config/comfyui/MODELS.md` (open licences only) into `<media.root>\comfyui\models`;
- turns on Open WebUI's image button: it writes the ComfyUI address, the saved workflow
  (`config/comfyui/workflows/z_image_turbo.json`) and its node map into Open WebUI's settings, after a backup
  `webui.db.bak-<time>-media`. Open WebUI reads them at once; reload the browser page.

From the command line: `uv run scripts/stack.py media check` (path guard and what is missing), `media install`,
`media provision`. `stack.py build` and setup stop with a "path guard" error when a media folder is outside
`agent_access.allowed_roots`.

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

On the new machine, clone the repository and run setup (step 2). It writes that machine's own `machines/<HOST>.yaml`,
which stays on that machine (do not commit it).
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
