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
- **Add features...**: opens the installer on its features page (see *Features* below).
- One line for each service: `● up`, `○ down`, `not installed` (its feature was not installed) or `not available yet`.
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

- **Services**: one row per service with its role, port and state: `Running (pid N)`, `Stopped`,
  `Off in settings` (turned off in the Settings tab), `Not installed` (its feature was not installed; **Start** is
  greyed out, amber when the profile still has it turned on) or `Not available yet` (Kokoro, which has no installer
  yet). Open WebUI, Phoenix and LiteLLM have an **Open** button. Every service except Ollama has **Start**/**Stop**;
  the Ollama app runs Ollama.
- **Loaded in Ollama**: each loaded model with **Size**, **On GPU** (share of the model in VRAM), **Context** and
  **Unloads** (when Ollama will drop it). "No model is loaded" is normal: the first request loads one.
- **Features**: one row per feature the installer offers, checked once a minute. Each row shows what the feature
  takes on this PC (`GPU 1.2 GB · RAM 0.4 GB · disk 0.3 GB · ~0.6 s per phrase`; the same figures as the installer)
  and its state:
  - `Installed` (green), or `Linked` for recordings (Claude Desktop starts the Whisper server) and `Gateway only`
    for OpenClaw;
  - `Installed, off` (grey): turned off in Settings;
  - `Not installed` (grey), or amber when the profile turns it on but its program is missing: run the installer again;
  - `Models missing` or `Model missing` (amber): the program is there, a model is not;
  - for OpenClaw, `Not set up`, `Bypasses the gateway` or `Uses an outside model`, with a **Use gateway** button that
    makes the gateway its only model provider ([details](choosing-drives.md#openclaw)).

  Under the rows, **Add features...** opens the installer, which starts on its features page with what you have. It
  reads **Open installer...** when everything is installed; the installer then checks and repairs what is there.
- **Hugging Face cache**: where `HF_HOME` points and how much it holds.
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
| Voice typing | **Voice typing hotkey**, **When to type**, **Cleanup**, **Stop after quiet**, **Language**, **Whisper model**, **Insert text by**, **Show the mic button** | See [Voice typing](#voice-typing). |
| Voice typing, under **Show advanced** | **Cleanup prompt** | The instructions the local model follows when it cleans up a dictation. See [Your own cleanup instructions](#your-own-cleanup-instructions). |
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
  menu keeps only the hotkey; bring it back with **Show mic** on the **Voice typing** row of the tray window's
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

### Your own cleanup instructions

The instructions the chat model gets are a setting. In the tray window, go to **Settings**, then **Voice typing**, and
click **Show advanced**. The **Cleanup prompt** box shows the built-in instructions until you change them. Edit them
there, for example add a line such as `- Use British spelling.` or `- Write numbers as digits.`, then click **Apply**.
Voice typing uses them from the next dictation, without a restart. **Restore default** puts the built-in text back
(Ctrl+Z undoes it until you apply). When your own instructions are saved, a note beside **Show advanced** says so.

Three things stay the same whatever you write:

- **Concise** adds its rule to shorten.
- The app adds the reply format (JSON with a `text` field), because it reads the answer from that field.
- The checks above still run. Instructions that ask for more than cleaning (summarise, translate, add a heading) can
  make the model's reply too long or too short, and then the transcript is typed instead (see
  [Troubleshooting](troubleshooting.md)).

The prompt is saved as `dictation.cleanup_prompt` in `machines/<HOST>.yaml`, as a block of lines; `''` means the
built-in text, so later improvements to it still reach you. If you edit the file by hand, run
`uv run scripts/stack.py dictate reload` so the running app reads it. `stack.py dictate transcribe` (**Try it on a
recording** above) uses the saved prompt too, so you can compare instructions on the same recording.

On the reference machine, adding `- Use American spelling and write every number as digits.` to the built-in text
took effect in 6 of 6 tries on the 9B, and the other rules still held (the self-correction "blue, no wait, green"
became "green" every time).

## Refine selected text

Rewrite text you selected in any app (Word, Logseq, Notion, a browser field) with the local model, and put the
original back within 30 minutes. It is part of the voice typing app, so it runs whenever voice typing runs.

1. Select the text.
2. Click the pencil button left of the mic button, or press **Ctrl+Alt+R**.
3. The pencil turns blue while the model works (about 1 to 2 seconds for a paragraph). Then the selection is replaced
   and the bubble shows the new text.

To pick the style each time instead, press **Ctrl+Alt+Shift+R** after selecting. A menu of every style opens at the
text cursor: press a number (**1** Polish, **2** Fix spelling and grammar only, and so on) or click a style, and the
selection is refined with it. **R** (Revert to the original) puts back the text of an earlier refine; **Esc** closes
the menu and leaves the text alone. Browsers, Electron apps such as Logseq and Notion, and some editors draw their own
text cursor and do not tell Windows where it is; there the menu opens at the mouse pointer. Change or turn off the key
with **Refine style menu hotkey** in the tray's Settings tab (`refine.menu_hotkey`; restarts voice typing).

To undo it right away, press **Ctrl+Z** in the app, as for any paste. To undo it later (within 30 minutes), select the
refined text, right-click the pencil and choose **Revert selected text to the original**. **Refine history...** in the
same menu lists the refines of the last 30 minutes, newest first: the text before and after side by side, removed
words struck through and added words underlined. **Copy original**, **Copy suggestion** and **Revert in the app** work
on the entry you pick. After 30 minutes an entry is deleted, and only the app's own undo can bring the original back.

Styles, all in the pencil's right-click menu: **Polish** (the default: fixes mistakes and smooths sentences), **Fix
spelling and grammar only**, **Concise**, **Professional**, **Friendly**, **Plain language** and **Bullet points**.
Clicking a style refines with it once; **Click and hotkey use** changes the default. To add your own styles, choose
**Add or edit styles...**. It opens `machines/<HOST>.yaml` (adding an example `refine:` section if there is none):

```yaml
refine:
  prompts:
    my-voice: Rewrite in my voice. Short sentences, active verbs, no jargon.
    email-reply:
      name: Email reply
      prompt: Turn my notes into a short, polite email reply. Keep every fact and date.
```

Save the file; the styles appear the next time you open the menu, no restart needed. An entry named like a built-in
style (`polish`, `grammar`, `concise`, `professional`, `friendly`, `simple`, `bullets`) replaces that style's
instructions.

How it works, all on this PC:

1. It presses Ctrl+C in the app to read the selection, then puts back what was on your clipboard.
2. The gateway alias `refine.model` (`local-primary`, the 9B on the reference machine) rewrites the text. With the
   style's instructions it gets fixed rules: keep the language; keep names, numbers, links, `[[page links]]`,
   `#tags`, `((block references))` and markdown; never answer a question in the text, only rewrite it.
3. The reply is checked. If it reads like an answer to you, grew or shrank far more than the style allows, or is empty,
   your text stays as it was. The suggestion still goes into the history.
4. It presses Ctrl+C once more. Only if the same text is still selected in the same window does it paste the new text
   over it. If you clicked elsewhere or switched windows meanwhile, nothing changes and the new text goes to the
   clipboard; the bubble says so.

The log is `.run\dictation\refine-log.jsonl`, one line per refine: time, app, window title, style, model, the text
before, the suggestion and what happened to it (replaced, rejected, copied, unchanged, cancelled). Unlike the voice
typing log it holds your words, so it holds them briefly: an entry is kept for 30 minutes (`refine.keep_minutes`, or
**Keep refine history for** in the tray's Settings tab), then deleted. The app checks once a minute, so an entry is
gone from the file within a minute of expiring, and the file itself goes when its last entry does. Deleted text can
stay in the drive's free space until it is overwritten. To forget everything at once, delete the file.

Good to know:

- **Right-click menus of other apps.** Windows has no shared right-click menu that a program can add to: Word, Logseq
  and Notion each draw their own. Refine therefore lives on its own button, its hotkeys, the button's menu and the style menu at the cursor.
- **Formatting.** The new text is pasted as plain text and takes the formatting where it lands. Bold, italics or links
  inside the selection are not kept. A selection with a picture or a table is refused, because pasting plain text
  would delete them.
- **Word.** Ctrl+Alt+R is Word's shortcut for the (R) sign; while voice typing runs, it refines instead. Choose another
  **Refine hotkey** in the tray's Settings tab if you need it. Selected paragraph marks are kept.
- **Logseq.** Select text inside the block you are editing (Ctrl+A selects the whole block). Selected blocks (Esc, then
  Shift+click) are copied as a list and do not fit.
- **Clipboard history.** Reading the selection uses the app's own copy, so the selected text shows up in Win+V history
  if that is on. The new text and your restored clipboard stay out of it.
- **Refused on purpose.** Terminals (Ctrl+C there could stop the running program), apps running as administrator
  (Windows blocks simulated keys), and the whole-line copy that VS Code, Notepad++ and Visual Studio make when nothing
  is selected. In VS Code, Cursor and JetBrains IDEs it copies with Ctrl+Insert, which cannot stop a program in their
  terminal panel; still, do not refine text in a terminal panel, where the new text would land on the command line.
- **Moving on.** If you switch to another app while the model works, it does not pull you back: the new text goes to
  the clipboard instead.
- **Limits.** Up to 10,000 characters at a time (`refine.max_chars`). Esc cancels while the model works; nothing is
  replaced then.
- **Settings.** The tray's Settings tab has a **Refine selected text** group: hotkey, default style, model, how long
  the history keeps an entry, and whether the pencil button shows. Every setting is under `refine:` in `machines/_defaults.yaml`. **Hide this button** in the
  pencil's menu keeps only the hotkey; **Show pencil** on the tray's **Voice typing** row, the tray menu's **Refine
  button (pencil)** item or **Show the refine button** in the mic button's menu brings it back.

## Read aloud

Have the text you selected in any app read to you by a voice on this PC. It is an optional part of the voice typing
app: tick **Read aloud (Kokoro)** in the installer (the tray's **Add features...**), or run

```
uv run scripts/stack.py read-aloud install
```

which adds espeak-ng and comtypes to voice typing's environment, downloads the Kokoro voices (about 0.35 GB into the
Hugging Face cache) and turns it on (`read_aloud.enabled: true`). Then restart voice typing (Stop and Start on its tray
row). Ticking read aloud in the installer ticks voice typing too, since it runs in that app. Without it nothing
changes: no speaker button, no hotkey.

1. Select the text.
2. Click the speaker button, right of the mic, or press **Ctrl+Alt+S**.
3. The button turns blue while the first sentence is prepared (under a second; about two the first time, while Kokoro
   loads), then shows a stop sign while it reads. The bubble shows the sentence being read and a line along the
   button's bottom edge shows how far it has got.

To stop, press **Ctrl+Alt+S** again, click the button, or press **Esc** (Esc belongs to read aloud only while it reads;
turn that off with **Esc stops reading** under Show advanced). Right-click the button for **Pause** and **Resume**,
**Read it again**, the **Voice**, the **Speed** (0.75x to 2x) and **Other languages get their own voice**.

Voices:

- **Kokoro** (Apache-2.0, 82 million parameters) speaks naturally in US and UK English, Spanish, French, Hindi,
  Italian and Brazilian Portuguese. It runs on the CPU, about three times faster than real time on the reference
  machine's Ryzen 5 5500, and uses no GPU memory. It holds about 0.5 GB of RAM while loaded and is freed after 30 idle
  minutes (`read_aloud.unload_after_min`). **Kokoro weights** under Show advanced picks fp32 (326 MB), int8 (92 MB and
  0.3 GB of RAM, as fast on this CPU) or off.
- **Windows voices** (David, Zira and Mark on an English Windows; any voice added in Windows Settings > Time & language
  > Speech) start at once and sound flatter. They cover the languages Kokoro does not.

Choosing a voice in the button's menu (a search list) plays a short sample in it and saves the choice
(`read_aloud.voice`). With **Other languages get their own voice** on, text that is clearly in another language is
read by a voice for that language: Kokoro's when it has one, else an installed Windows voice; the bubble says which.
Thai, Russian, Japanese and other scripts are recognised by their letters; Latin-script languages by common words, so
a short phrase keeps your chosen voice. Pick per-language voices in the machine file:

```yaml
read_aloud:
  voices: {fr: ff_siwis, de: 'windows:Microsoft Katja'}
```

`uv run scripts/stack.py read-aloud voices` lists every voice id; `read-aloud speak "Some text" --voice bf_emma` says
it (or writes a WAV with `--out file.wav`), with the time each piece took.

How it works, all on this PC:

1. It presses Ctrl+C in the app to read the selection, then puts back what was on your clipboard, as refine does.
   Pictures and tables in the selection are fine: only the text is read.
2. The text is cleaned for listening: Markdown and Logseq markup (`**bold**`, `[[page links]]`, `#tags`,
   `key:: value` properties, block references) is dropped, a link is read as its site's name, and every list item or
   heading gets a short pause.
3. It is cut into pieces of a sentence or a few. The first piece is one sentence, so the voice starts quickly; the
   next ones are prepared while it speaks, at most 8 seconds of speech ahead.
4. Nothing is saved: the text stays in memory for **Read it again** until the app quits. The tray's Usage tab counts
   each reading (seconds of speech, the voice, the time it took to make), never the words.

Good to know:

- **Not installed or half installed.** With read aloud on but its packages missing, the button says so and how to
  add it. If Kokoro's weights are missing or Kokoro fails to load, a Windows voice of the same language reads instead
  and the bubble says why. Reading never starts a download.
- **Voice typing first.** Starting to dictate stops a reading, so the microphone does not hear the voice. Read aloud
  waits while you dictate.
- **Refused on purpose,** as for refine: terminals (Ctrl+C there could stop the running program) and apps running as
  administrator.
- **Ctrl+Alt+S** splits the window in Word and opens Settings in JetBrains IDEs; while voice typing runs, it reads
  instead. Choose another **Read aloud hotkey** in the tray's Settings tab (restarts voice typing).
- **Limits.** Up to 20,000 characters at a time (`read_aloud.max_chars`); a longer selection is cut at a sentence and
  the bubble says so.
- **Settings.** The tray's Settings tab has a **Read aloud** group: on or off, hotkey, voice, speed and the
  per-language switch; Show advanced has Esc and the Kokoro weights. Every setting is under `read_aloud:` in
  `machines/_defaults.yaml`. **Hide this button** in the speaker's menu keeps only the hotkey; **Show speaker** on the
  tray's **Voice typing** row, the tray menu's **Read aloud button (speaker)** item or **Show the read aloud button**
  in the mic button's menu brings it back.

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
