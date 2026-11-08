# Refine a Logseq block from its right-click menu

Date: 2026-11-08. Status: built on branch `claude/sleepy-perlman-c4c162`, on top of the refine branch
(`claude/ai-text-refinement-contextmenu-70d19f`, PR #44). Verified in a throwaway copy of Logseq 2.0.2 with its own
profile and graph (details below); not yet loaded in the owner's Logseq.
Manual: [user-guide.md, "Refine a Logseq block from its right-click menu"](../../manuals/user-guide.md#refine-a-logseq-block-from-its-right-click-menu).
Code: `integrations/logseq-refine/` (the plugin and its end-to-end test), `scripts/stacklib/dictation/pluginapi.py`
(voice typing's side), `scripts/stacklib/logseq_plugin.py` (build, key, tray row).

## Ask

Follow-up R2 of [Refine selected text in every app](2026-11-07-refine-selection.md): an item in Logseq's own block
right-click menu, "Refine with <style>", that rewrites the block with the stack's local model, using the same styles
and the same refine log as the voice typing app's pencil button.

## Decisions

| # | Question | Choice | Why; what was turned down |
|---|---|---|---|
| L1 | What the plugin adds | Block right-click menu: **Refine with <default style>**, optional extra styles (setting), **Refine with...** (a style picker in the plugin's frame) and **Put back the original (undo refine)**; slash command `/Refine this block` | `logseq.Editor.registerBlockContextMenuItem` is the one real right-click entry point Logseq offers. Menu items cannot be removed once registered, so the labels are set at start-up and the picker carries the full, current list. |
| L2 | How the plugin reaches the model | A `/plugin/` route on voice typing's control server (`pluginapi.py`), which calls `refine.refine_text` with the profile's `refine.model` | Same styles (`refine.prompts` read per request), same checks, same log, same model as the pencil. Calling the LiteLLM gateway from the plugin was turned down: a plugin cannot write `.run/dictation/refine-log.jsonl` or read the machine file, the gateway has only its master key (virtual keys need Postgres), and the call would not be counted as a refine in the Usage tab. Voice typing has to run; the plugin says so when it does not. |
| L3 | Getting past the control server's rule against web pages | No exception to the rule: the plugin sends through `logseq.Request`, which Logseq's main process performs with node-fetch, so the request has no Origin header. Host and Origin checks stay first. | The probe showed the headers (`user-agent: node-fetch`, no Origin, Authorization passed through). Allowing the plugin's iframe origin (`lsp://logseq.com`) with CORS was turned down: it would weaken the one rule that stops web pages, and it needs preflight handling. |
| L4 | Who may call the routes | `REFINE_BEARER` (.env), compared in constant time and read per request; the owner pastes it into the plugin's settings. **Set up** and **Copy key** on the tray row and `stack.py logseq-plugin` put it on the clipboard, kept out of clipboard history; the tray empties the clipboard after 60 s unless something else was copied. | The routes add refine log entries, so callers need a key; a separate key from `DICTATION_BEARER` keeps each to one purpose. Other Logseq plugins share the main window's origin and can read this plugin's settings, so the key stops web pages and other programs but not other Logseq plugins. That is why plugin entries (`source: plugin`) are never offered to the pencil's selection-based Revert or History's Revert in the app (`refinelog.revertable_in_app`); they are undone block by block from Logseq. A program that takes the port while voice typing is down would receive the key; this is accepted as for the transcription endpoint, because a program running as the owner can read the key from Logseq's settings file anyway. The stack writing the key into Logseq's settings files was turned down: it only reads `~/.logseq/preferences.json` to show whether the plugin is loaded. |
| L5 | Which text goes to the model and back | `fullTitle`, the block as Logseq shows it (links and tags by name), written back the same way with `updateBlock` | In database graphs `title` stores refs by id (`[[<uuid>]]`, `#[[<uuid>]]`). Writing that id form back made Logseq 2.0.2 create a new tag named after the uuid; writing names resolved to the same ids and created nothing (checked in the sandbox). Block references stay `((uuid))` in both forms. |
| L6 | Keeping Logseq markup | Property-like lines (`key:: value`) are not sent and come back untouched; page links, tags, block refs, macros, code, images and URLs must come back as a multiset, else the suggestion is rejected and logged | The prompt already asks for it (RULES in refine.py); the check makes it a guarantee. In database graphs `key:: value` is plain text, not a property, but keeping it verbatim costs nothing. |
| L7 | Never changing a block without a log entry | Log first, then write: `/plugin/refine` returns a suggestion and a token; the plugin reads the block again and calls `/plugin/commit` (write true when unchanged, whitespace aside); voice typing logs the entry; only then does the plugin call `updateBlock`. A suggestion never committed is logged as skipped after 10 minutes or when voice typing stops. | Logging after the write (as the pencil does after its paste) would leave a replaced block without an entry if voice typing stopped in between. A block you edited while the model worked keeps your edit. A block you are typing in when the suggestion comes back is left alone too, because its saved text may lag behind the editor and the editor would save over the new text. Either way the suggestion is logged as skipped. |
| L8 | Undo | **Put back the original** finds the newest replaced, not yet reverted refine of that block uuid (same graph), needs the block to be at least 0.8 similar to the suggestion, and goes through the same log-then-write step as `kind: revert` | Works later and after other edits, without Logseq's undo history; the message says when edits made after the refine were undone too. |
| L9 | Building the plugin | No bundler: `src/` (index.html, core.js, main.js, style.css) plus `@logseq/libs`' `lsplugin.user.js`, copied into `dist/` by `build.mjs` after `npm ci`. `@logseq/libs` pinned to 0.3.3, the version Logseq 2.0.2 ships. `dist/` is not committed. The page's CSP allows only its own scripts and no connections. | npm's `latest` tag for `@logseq/libs` is still 0.0.17 (file graphs); the database version is under `next`. Committing the minified library was turned down (third-party build output, no licence field in its package). |
| L10 | Testing without the owner's Logseq | `e2e/sandbox.mjs`: a copy of the installed app whose `app.asar` is renamed so Electron starts `resources/app/boot.js` first; boot.js points home, appData and userData into `.run/logseq-test`, hides the window off-screen, blocks `logseq://` registration and updates. `e2e/run.mjs` drives it over DevTools: real right-clicks on bullets, menu clicks, key presses. `e2e/server.py` serves the real plugin API with a fake model or a private gateway. | Environment variables cannot move `~/.logseq` (Windows ignores USERPROFILE for the profile folder), and Electron looks for `app.asar` before an `app` folder; the first try therefore read the owner's plugin list (it wrote nothing; see Measurements). `start` now refuses a copy that still has `app.asar` and stops the copy unless boot.js reports the sandbox home. DevTools listens on a port Chromium picks; `clean` and the run's reset delete only a folder that `prepare` marked. |
| L11 | Limits against a misbehaving caller (from the security review) | Up to 8 runs of text between property lines per block, and one deadline (`refine.timeout_s`) for all of them; at most 64 suggestions waiting for a commit; revert text up to twice `refine.max_chars`, one revert at a time (its comparison is pure Python); the plugin waits as long as voice typing's own model timeout says | Without them one request could hold the GPU for hours (a block of alternating text and property lines), and a loop of reverts could pile up waiting entries or stall the app's threads. |

## Measurements (2026-11-08, on the owner's PC)

- Logseq 2.0.2 facts found in the sandbox: block `title`/`content` hold refs by id and `fullTitle` by name; database
  graphs keep `key:: value` as text; plugin iframes load from `lsp://logseq.com/external/<path>`; toasts render as
  `.ui__toast`; the `/` menu opens only on a `/` key typed at the start or after a space; `edit_block` leaves the
  cursor at the start. Logseq 2.0.2 opens database graphs only; Markdown graphs can only be imported.
- End to end with the fake model (`run.mjs --mode fake`), 29 checks, all passed (last run after the review fixes):
  - plugin load, and the graph inside the sandbox;
  - menu items; refine with Polish; links and tags still pointing at the same pages; no page created; the log entry;
  - Put back the original, and its log entry;
  - a property line kept; no change needed; a tag dropped by the model rejected and logged;
  - an edit made during the model call kept, with the suggestion logged as skipped;
  - a block you are typing in left alone, with the suggestion logged as skipped;
  - the picker listing all styles with the first focused, and picking Concise;
  - the slash command typed into a block;
  - a wrong key changing nothing and saying how to fix it.
- With the real model through a private copy of the gateway (port 4010, this branch's config, a throwaway master key,
  traces under `.run`): qwen3.5:9b refined a 103-character block in 2.4 s from the click to the log entry. "this are
  a block that mention [[Project Alpha]] and #idea, writen in a hurry and with to many typo" became "This is a block
  that mentions [[Project Alpha]] and #idea, written in a hurry and with too many typos." Refs were intact and Put back
  restored it. The gateway trace named the client `agent-stack-logseq-refine`.
- Ollama's own OpenAI-compatible endpoint ignores `think: false`: two refines through it ran out of tokens while
  thinking. The gateway is needed in front of qwen3.5 for this request shape.
- The real voice typing app, started from this branch under a throwaway profile (port 8791, no buttons, no refine
  hotkey):
  - `/health` reported `"plugin": {"key": true}`;
  - `/plugin/styles` returned the seven styles;
  - an Origin header got 403 and a wrong key 401.
  - Its refine went to the owner's live gateway on port 4000, which had come up meanwhile, and was stopped before it
    answered. That one test request is in the owner's gateway traces under `agent-stack-logseq-refine`.
  - The test profile's `D:\huggingface` lacked Whisper, so the app downloaded large-v3-turbo (1.6 GB) there. The
    owner's live setup now keeps it in `C:\huggingface`.
- Tests:
  - 48 Python tests in `tests/test_pluginapi.py`, plus one in `tests/test_refine.py` (a planted plugin entry is never
    pasted by the pencil's Revert);
  - 12 Node tests in `integrations/logseq-refine/test/`.
  - The real-model run and the real-app run came before the review fixes; the fixes did not touch the model call or
    the app's wiring.
- An independent security review (a read-only agent) found three medium issues, all fixed:
  - the key is readable by other Logseq plugins, and planted entries could reach the pencil's Revert (L4);
  - one request could hold the GPU (L11);
  - a block being typed in could be overwritten (L7).
  It also found low ones, all fixed except one:
  - fixed: the revert size; the cap on waiting suggestions; the key in clipboard history; the sandbox's unchecked
    delete, inherited `ELECTRON_RUN_AS_NODE`/`NODE_OPTIONS`, paths with spaces and fixed DevTools port; messages that
    began with server text.
  - accepted: port squatting (L4).
- The owner's `~/.logseq` was checked after every sandbox run. Its only writes came at 01:52 from the owner's own
  Logseq restarting (a new main process at 01:52:07), and none mention a test path.

## Not verified

- The plugin in the owner's own Logseq and graphs, by design. Logseq's own Developer mode switch and **Load unpacked
  plugin** dialog were not clicked: the test registers the folder in `preferences.json` and seeds the settings file
  `settings/agent-stack-refine.json`, which is what that dialog and the gear write.
- The picker's look in light and dark themes (no screen capture), arrow-key moves in it, and Logseq's own Ctrl+Z after
  a plugin refine.
- A full refine through the real voice typing app with a model answering; the plugin API and the gateway were covered
  separately, as were the app's routes and key.
- The tray row in the live tray, which was rendered hidden from this worktree: Set up, Copy key and the states read
  back through Tk. Set up's clipboard copy was not run on the owner's clipboard.
- Multi-block selections; blocks longer than a few hundred characters; languages other than English.

## Follow-ups worth considering

- A selection context menu item for several selected blocks, refining each and logging each.
- Pairing instead of pasting the key: the plugin asks, and voice typing shows Allow in its own bubble. Signing each
  request and answer with the key (HMAC) instead of sending it would also defeat a program that takes the port while
  voice typing is down.
- From the review, about code this work did not add: the control server's actions (`/start`, `/revert`, `/quit`, ...)
  need no key. Any local program can send them, Logseq plugins included, because their requests come from Logseq's
  main process. Requiring a key for actions, as for transcription and the plugin routes, would close that.
- A Word add-in or a browser extension on the same `/plugin/` routes; the routes take any `app` name.
