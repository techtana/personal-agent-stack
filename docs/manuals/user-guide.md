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

Counts every model the stack ran, local or outside API:

- Gateway requests (chat, titles, document embeddings, Claude Code profile B, OpenClaw, the orchestrator, voice
  typing's clean-up), read from `traces/litellm/<date>.jsonl`.
- Models that run outside the gateway, each written to `traces/usage/<source>/<date>.jsonl`:
  - Whisper in voice typing (the live previews shown while you speak re-read the phrase so far, so they are listed
    under the table and kept out of the totals), including the microphone in Open WebUI's chat box once it uses voice
    typing's Whisper (client **Open WebUI**);
  - Whisper in the recordings server that Claude Desktop uses;
  - images made by ComfyUI (the tray reads ComfyUI's job history every few seconds while ComfyUI runs);
  - `stack.py bench` and the start-up warm-up.

What is in the tab:

- **Period**: **Today**, **7 days** (default) or **30 days**.
- **Group by**: **Model** (the model that did the work, such as `qwen3.5:9b`, `large-v3-turbo` or
  `Z-Image-Turbo int8`; the default), **Alias or service** (the gateway name the client asked for, such as
  `local-primary`, or the service that ran the model, such as **Voice typing** or **ComfyUI**) or **Client** (who
  asked, such as **Open WebUI**, **Claude Code**, **Voice typing** or **Claude Desktop**). Each row opens into its
  clients (into its aliases and services when grouped by client).
- Tiles: **Requests**, **Tokens in / out**, **Speech audio**, **Images**, **Errors** (red when above 0) and **API
  cost**. Local models cost $0; cost is what outside APIs charge.
- The table has **Requests**, **Errors**, **Input**, **Output**, **Avg time**, **Speed**, **Overall**, **Cost** and
  **Last used**. Input, output and speed are in the units of the row:
  - chat and embeddings: tokens, and tokens per second while generating;
  - speech: seconds or minutes of audio, and how many times faster than real time (for example `28x`);
  - images: images made, and seconds per image.

  **Overall** adds the time spent loading the model and waiting in the queue. An outside API's row ends in `· API`.
  Click a heading to sort. A red row means every request in it failed.
- The line under the table says what the selected row's requests were and where their time went.
- **Not counted** names model use the tab cannot see yet, while it can happen. On an existing install that is the
  microphone in Open WebUI's chat box, which runs Open WebUI's own Whisper, and Open WebUI's document embeddings, both
  until the provisioning step below. It also names a speech-to-text engine outside the stack, if one is chosen in
  Open WebUI's **Admin Settings > Audio**.
- The chart shows requests per day for all models together. Select a row to see that row in its own unit: tokens,
  minutes of audio, or images per day.

`uv run scripts/stack.py usage --days 7` prints the same table in a terminal (`--by alias|client`; `--clients` for
the sub-rows).

If the table says "No model was used in this period", either nothing ran a model in that period or **Write usage
traces** is off in Settings. That switch also stops the usage records, including those of programs that were already
running (they find a `RECORDING_OFF` file in `traces/usage`). Records hold the model, times, sizes and counts, and
the type of an error, never a prompt, transcript, image or file path.

Two steps apply this to an existing install:

- On a fresh install, Open WebUI's document embeddings go through the gateway, and its chat-box microphone goes to
  voice typing's Whisper while voice typing is on (see [Voice typing](#voice-typing)); both are counted. On an
  existing install, run `uv run scripts/stack.py media provision`: it backs up Open WebUI's database, then writes both
  settings. Restart Open WebUI for the embeddings; the microphone switches with the next recording.
- Recordings are counted once `uv run scripts/stack.py whisper install` has been run again from the main checkout
  (a worktree would point the records at its own folder): it copies the new server and adds its usage folder to
  Claude Desktop's config. Restart Claude Desktop afterwards.

*Settings*

Changes the most common values in your machine profile, `machines/<HOST>.yaml`, without editing the file.

| Group | Setting | What it does |
|---|---|---|
| Models | **Primary model**, **Primary context (tokens)** | The model behind `local-primary` and every `<department>-local`, and its context size. |
| Models | **Memory-map primary weights** | Needed for the 35B MoE model; leave off for dense models. |
| Models | **Small model**, **Small context (tokens)** | The model behind `local-small`. Keep the context equal to the primary's when both use the same model. |
| Tracing and services | **Write usage traces** | Writes `traces/litellm/` and `traces/usage/`. The Usage tab and `retro` need it. |
| Tracing and services | **Phoenix tracing** | Runs Phoenix. Leave off on the reference machine: Smart App Control blocks it. |
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
  period reloads the model, which takes about 2 minutes from the USB drive on the reference machine.

| Service | Address | What it is for |
|---|---|---|
| Ollama | http://127.0.0.1:11434 | Runs the local models on the GPU. |
| LiteLLM gateway | http://127.0.0.1:4000 (admin UI at `/ui`) | Sends each request to a local or cloud model. |
| Phoenix | http://127.0.0.1:6006 | Shows a trace of every request. |
| Orchestrator MCP | http://127.0.0.1:8765/mcp | Lets agents hand tasks to departments. |
| Open WebUI | http://127.0.0.1:3000 | A chat interface. |
| ComfyUI | http://127.0.0.1:8188 | Makes images for the chat's image button; its own page edits workflows. |

## Making images

When ComfyUI is installed (the installer's media option, or `uv run scripts/stack.py media install`), Open WebUI's
image button works:

1. In a chat, click **Image** under the message box (or ask the model to draw something; Open WebUI turns the
   request into an image prompt), then send your description.
2. The image appears in the chat. The first one after a start or a GPU switch takes about 30 s on the reference machine while
   the model loads from D:; later ones take about 11 s at 1024 x 1024.

The model is Z-Image-Turbo (Apache-2.0) with 8 steps. Images are saved in `<media.root>\outputs\open-webui`.
Change the size or steps in `machines/<HOST>.yaml` under `media:` (`image_size`, `image_steps`), then run
`uv run scripts/stack.py media provision`.

Chat and images share the 12 GB card. The tray's **GPU** card has two buttons: **Media** unloads Ollama's models
so image jobs get the whole card, and **Chat** asks ComfyUI to free its memory so the next chat loads quickly. Image
generation also works without switching: ComfyUI runs with `--lowvram` and moves weights to RAM when the chat model
holds the card, which is slower.

The chat model itself (`local-primary`) still cannot draw; it is a text model. "Draw me a picture" in a plain chat
gets a text answer unless the image button is on.

## Voice typing

Speak instead of typing, in any app: Logseq, Word, Notion, a browser text field, Open WebUI. Whisper runs on this
PC (on the GPU when it can) and the cleanup uses the gateway's local model, so nothing leaves the machine.

Set it up once with `uv run scripts/stack.py dictate install`. It builds its own Python environment under
`<media.root>\dictation`, fetches the Whisper model into `HF_HOME` if it is not there yet (1.6 GB) and turns voice
typing on in `machines/<HOST>.yaml`. From then on the tray starts it with the other services (the **Voice typing** row
on the Overview tab). To start it right away: `uv run scripts/stack.py dictate start`.

1. Click where the text should go.
2. Press **Ctrl+Alt+D**, or click the round mic button at the bottom right, and speak. The button turns red, and the
   bubble above it shows what Whisper hears.
3. Stop talking. After 3 seconds of quiet it stops by itself; or press Ctrl+Alt+D again. To talk only while you hold
   the keys, hold Ctrl+Alt+D. **Esc** cancels.
4. The text appears at the caret.

Two modes, chosen with a right-click on the button (or in the tray's Settings tab):

- **Type when I finish, cleaned up** (the default, `polish`): the local model removes um, uh, "you know", false starts
  and self-corrections ("Tuesday, no wait, Wednesday" becomes "Wednesday") and fixes punctuation. **Concise** also
  shortens sentences; **Verbatim** types exactly what Whisper heard. It adds about a second after you stop.
- **Type as I speak** (`live`): each phrase is typed when you pause for 0.7 seconds. Only the filler sounds (um, uh)
  are removed; there is no model cleanup.

How the text is made: two models, both on this PC.

1. **Whisper writes down what was said.** faster-whisper (`dictation.model`, `large-v3-turbo` by default) transcribes
   each phrase when you pause, verbatim, fillers included. It gets the text so far as a prompt (for continuity) and
   `dictation.vocabulary` as hints. Whisper does not clean or shorten anything.
2. **The chat model cleans it up (polish mode, Clean or Concise only).** When you stop, the joined transcript goes
   to the gateway alias `dictation.cleanup_model` (`local-small`, the 9B in Ollama on the reference machine), with
   instructions to remove fillers and false starts, keep only self-corrections, fix punctuation, keep your words and
   meaning, and never answer what you said. Concise also asks it to shorten. The request uses JSON output and turns
   the model's thinking off (with thinking on, the 9B returned nothing after 49 s).

The reply is checked before it is typed. If it grew, shrank too much or reads like an answer, or the gateway does not
answer, the raw transcript is typed instead, with only um/uh/er removed by a simple text rule (no model).

| Mode | Whisper | Chat-model cleanup |
|---|---|---|
| Polish, Clean or Concise | yes | yes |
| Polish, Verbatim | yes | no |
| Live | yes | no (only the um/uh rule) |

On the reference machine (RTX 3060 with the 9B chat model loaded) Whisper takes 0.3 to 0.5 s per phrase and the
cleanup about 1 s. Whisper holds about 1.2 GB of VRAM and frees it after 30 idle minutes; the next dictation loads it
again (5 s, while you are already talking).

Good to know:

- **Pasting.** The text goes in with Ctrl+V: the clipboard is saved first and restored a second later, and your
  dictations stay out of clipboard history (Win+V). For an app that blocks pasting, choose **Insert by: typing** in the
  button's menu. Typed keystrokes can double brackets in Logseq, which pairs them automatically; pasting does not.
- **The right window.** If you switch windows while it works, it does not type into the new window: the text goes to
  the clipboard and the bubble says so. Programs running as administrator cannot receive typed input from a normal
  program, so their text goes to the clipboard too. In live mode with the hotkey held down, the phrases are typed when
  you let go (keys still held would turn Ctrl+V into Ctrl+Alt+V).
- **Privacy.** The microphone is open only while the button is red (Windows shows its microphone icon in the taskbar
  then). Audio stays in memory and is never saved; the log keeps lengths and timings, not words.
- **Names and jargon.** Add words Whisper should expect to `dictation.vocabulary` in `machines/<HOST>.yaml`, for
  example `vocabulary: 'Logseq, LiteLLM, Ollama'`. In a test, "Logseq" came out as "Logsake" without it.
- **Language.** It is detected from your first phrase. If short phrases come out in the wrong language, set one:
  **Language** in the button's menu (or on the tray's Settings tab) opens a search box over all 100 languages the
  Whisper model knows. Type part of a name, another common name or a code (`nor`, `farsi`, `pt`), move with the arrow
  keys and press Enter, or click a language. Esc closes it. English-only models (`small.en`, distil) offer English only.
- **Hotkey.** Ctrl+Alt+D by default, because the Claude desktop app uses Ctrl+Alt+Space for its quick entry. Change
  it in the tray's Settings tab. If another program already has the key, the bubble says so at start; the button still
  works.
- **Starting and hiding.** The tray starts voice typing with the other services. **Hide button** in the button's
  menu keeps only the hotkey; bring it back with **Show button** on the **Voice typing** row of the tray window's
  Overview tab, or the tray menu's **Voice typing button** check item. Either one switches it at once and remembers
  the choice (`dictation.button`).
- **Try it on a recording.** `uv run scripts/stack.py dictate transcribe note.wav --style concise` prints each phrase,
  the transcript and the cleaned text. `stack.py dictate check` lists the microphones and shows whether the GPU is used.
- **Open WebUI's microphone.** While voice typing runs, the mic in Open WebUI's chat box uses the same Whisper
  (`dictation.model` on the GPU) instead of Open WebUI's own small Whisper `base`. Audio files dropped into a chat use
  it too.
  - Open WebUI sends each recording to `http://127.0.0.1:8790/v1/audio/transcriptions` with voice typing's own key,
    `DICTATION_BEARER` in `.env` (not the gateway's key, so a program that takes the port while voice typing is off
    learns nothing that opens the gateway). It arrives as webm, ogg or mp4 from the browser, or as the file's own
    format. Each one is counted in the tray's Usage tab under client **Open WebUI**.
  - A fresh install is set up for it. On an existing one, run `uv run scripts/stack.py media provision` once: it adds
    the key to `.env` (the rest of the file stays as it is) and points Open WebUI at voice typing.
  - The language is detected for each recording unless Open WebUI's own **Speech-to-Text Language** setting names one.
    Voice typing's **Language** setting is for dictation only.
  - Open WebUI gets Whisper's words as heard; the chat-model cleanup is only for text typed into apps.
  - Limits: 25 MB and 30 minutes of audio per file (longer recordings belong to the recordings server), and one file
    at a time. Whisper is shared with dictation, so a long file holds a dictation until it is done.
  - If voice typing is stopped, Open WebUI's mic shows a connection error. Start voice typing again, or set
    **Speech-to-Text Engine** back to **Whisper (Local)** in Open WebUI's **Admin Settings > Audio**.

Every setting is under `dictation:` in `machines/_defaults.yaml`; copy a line into `machines/<HOST>.yaml` to change it.

## Working with the departments

There are six department agents: `app-dev`, `testing`, `security`, `devops`, `code-review` and `docs`.

**In Claude Code (your subscription)**

- Open this repository in Claude Code. The departments appear as subagents. Mention one by name: `@security review src/auth.py`.
- Run one department as the main agent: `claude --agent docs`.
- Skills: `/retro`, `/harden`, `/brainstorm`, `/why-routed`, `/ux-rules` to review a screen, page or flow against
  a researched catalog of UX rules (for example `/ux-rules scripts/tray.py`), and `/claude-security-audit` (see
  [Checking your Claude setup](#checking-your-claude-setup)).
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

## Your skills library

Skills you write in `~/.claude/skills` or in claude.ai are copied into `skills/` by the weekly `skills-sync`
scheduled task (set up in the installation manual, step 8). To run it by hand:

```powershell
uv run scripts/stack.py skills-sync --dry-run   # report only
uv run scripts/stack.py skills-sync             # copy new and changed skills
```

The report names each skill as:

- `added`: new, now copied into `skills/`.
- `updated`: changed at its source; the copy in `skills/` was replaced.
- `unchanged`: nothing to do.
- `orphaned`: gone from its source (deleted or renamed). The copy stays until you delete it in a commit.
- `skipped`: Anthropic's, proprietary, or listed under `exclude` in `skills/sync.yaml`.

Edit a skill at its source, not in `skills/`; the next sync overwrites the copy. The weekly task holds back any skill
whose new content looks personal and names it in its report. To keep it out for good, add its name to `exclude`.

## Checking your Claude setup

`/claude-security-audit` checks Claude Code and Claude Desktop on this computer for privacy and safety, and removes
your identity from what Claude writes. A weekly scheduled task runs it on Monday mornings; you can also run it any
time by asking Claude Code for it in this repository.

It looks at:

- **Versions:** whether your Claude Code installs (the command line, the VS Code extension and Claude Desktop's own
  copy) are behind, and whether a published advisory affects them.
- **Data leaving the computer:** telemetry, error reports, `/feedback` uploads and claude.ai connectors.
- **Retention:** how long conversation transcripts stay on this computer.
- **Access:** whether Claude can read credential files, and allow rules that let it run anything of a kind unasked.
- **Extensions:** MCP servers, plugins and hooks, and anything that changed since the last audit.
- **New settings:** what Claude Code's docs and changelog have added since the last audit.
- **Your identity:** your email, name or Windows user name in repositories, `CLAUDE.md`, Claude's memory, skills and
  scheduled tasks, and scripts that send an email address to web APIs.

What it does about them:

- **Settings:** it never changes them. The report gives the exact setting and file for each fix, and you apply it.
- **Identity:** it replaces your identity with placeholders such as `you@example.com`, `Your Name`, `%USERPROFILE%`
  and `%USERNAME%`. A scheduled run opens a pull request for this repository and fixes Claude's own files in place.
  Files with uncommitted changes and skills that hold personal data on purpose are left alone.
- **Reports:** each run writes one to `%LOCALAPPDATA%\claude-security-audit\reports\`, outside every repository.
  Nothing identifying goes into it.

What it cannot do: stop Claude Code or Claude Desktop from sending your prompts, files and account details to
Anthropic. Only managed settings, the sandbox (WSL2 on Windows) or the local-only profile B
(`scripts/claude-local.ps1`) enforce anything.

A standing rule in `~/.claude/CLAUDE.md` tells every session to keep your identity out of what it writes. Its text is
in `.claude/skills/claude-security-audit/references/identity.md`.

To set up the weekly run on another computer, create the scheduled task from
`.claude/skills/claude-security-audit/scheduled-task.md` in the Claude desktop app (**Scheduled tasks**, weekly,
Monday 09:30).

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

Traces are written to `traces/litellm/` (gateway), `traces/usage/` (models run outside the gateway: Whisper,
ComfyUI, direct Ollama calls) and `traces/claude/` (Claude Code hooks). The tray's **Usage** tab and `stack.py usage`
summarise the first two. Gateway traces also appear in Phoenix when Phoenix runs.
