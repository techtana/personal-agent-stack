# Refine selected text in every app

Date: 2026-11-07. Status: built on branch `claude/ai-text-refinement-contextmenu-70d19f`; verified on the reference
machine in test windows, a throwaway Word document and Edge text fields (details below); not yet used in Logseq or
Notion.
Manual: [user-guide.md, "Refine selected text"](../../manuals/user-guide.md#refine-selected-text). Code:
`scripts/stacklib/dictation/` (`refine.py`, `refinelog.py`, `selection.py`, `refiner.py`, `history.py`, `overlay.py`).

## Ask

The owner wants to highlight text in any app (Word, Logseq, Notion and the like), send it to the AI to be refined by a
chosen system prompt, and have the result replace the highlighted text. They asked for an item in the right-click menu,
or a button next to the voice typing button. A log of the text before and the suggestion after must always be kept,
so a change can be reverted.

## Decisions

| # | Question | Choice | Why; what was turned down |
|---|---|---|---|
| R1 | Where it lives | Inside the voice typing app: same process, same tray row, its button bar, hotkey thread and clipboard thread | The app already has a window that never takes the focus, global hotkeys, safe clipboard handling and the elevation check (docs/design/plans/2026-11-07-voice-typing.md V9-V11). A second resident app would repeat all of it. |
| R2 | How you start it | A pencil button left of the mic (same no-activate window), a hotkey (Ctrl+Alt+R), and the pencil's right-click menu for styles, revert and history | No shared right-click menu exists in Windows: each app draws its own, and shell extensions reach only Explorer. A low-level mouse hook that swallows right-clicks to show our own menu was turned down (adds latency to every click system-wide; Windows drops a slow hook silently). App add-ins (a Logseq plugin, a Word add-in, a browser extension) each cover one app and are follow-ups. |
| R3 | Reading the selection | Ctrl+C, with the clipboard saved before and put back right after; Ctrl+Insert in editors with a terminal panel inside (VS Code, Cursor, JetBrains IDEs, Visual Studio) | UI Automation's TextPattern was turned down: Chromium and Electron apps expose it only after turning on their accessibility tree, which slows them, and Word's is slow on long documents. Ctrl+Insert is Copy in those editors and cannot interrupt a program running in their terminal panel. |
| R4 | Replacing it safely | Press Ctrl+C again just before pasting; paste only if the same text (whitespace aside) is still selected in the same window, that window is still in front and the copy is not an editor's whole-line copy; otherwise put the new text on the clipboard and say so. The focus is taken back only from a window of this app (a menu, the history window), never from another app you moved to | Catches a click elsewhere or a window switch while the model works. A check after the paste (a third Ctrl+C) was turned down: with nothing selected, Ctrl+C in a terminal, VS Code's included, interrupts the running program. |
| R5 | What is refused | Terminals; apps that may run as administrator (UIPI drops simulated keys); a copy whose selected HTML fragment (between StartFragment and EndFragment, so a table around a selected cell does not count) holds img, table, svg, video, iframe, object or embed; an editor's whole-line copy (Scintilla and Visual Studio clipboard formats, VS Code's `isFromEmptySelection`); a clipboard over 64 MB that cannot be saved; more than `refine.max_chars` | Each would lose data or paste in the wrong place: plain text over a picture deletes it; a whole-line copy with no selection would paste a second copy of the line. |
| R6 | Model call | `refine.model` (`local-primary`, private), JSON mode, `think: false`, temperature 0.3, `max_tokens` 2 per character + 400 (at most 8192), 120 s timeout | Same lessons as the voice typing cleanup: thinking made the 9B return nothing; JSON mode keeps the gateway's model label off the text. |
| R7 | Styles (system prompts) | Seven built-in styles with length limits each; your own under `refine.prompts` (text, or `{name, prompt}`); a built-in id replaces that style's text but keeps its limits; read from the machine file at every use | The owner asked for "a certain system prompt": a default plus a menu, and new ones without a restart. |
| R8 | Checks on the reply | Rejected when empty, when it starts like a reply to you ("Sure!", "Certainly,", a refusal, or "Here is ...:" with a colon), when longer than max_ratio x n + 100 or, for selections over 80 characters, shorter than min_ratio x n. Tags, labels, quotation marks and JSON debris are taken off; whitespace around the selection and Windows line breaks are kept | A selected question must come back as a better question, not an answer. "Here's" alone was a false positive (below). |
| R9 | The log | `.run/dictation/refine-log.jsonl`: every outcome (replaced, copied, rejected, unchanged, cancelled, failed, skipped) with before, after, app, window title, style, model and seconds; append-only, never trimmed | The owner asked to always keep before and after. It holds text on purpose, unlike `dictation.log` (lengths and timings only, V13); it never leaves the machine. |
| R10 | Revert | Select the refined text; the newest log entry whose suggestion matches it (difflib ratio 0.9, or 0.8 for the entry picked in History) gives the original, pasted with the selection's own surrounding whitespace; logged as `kind: revert` | Works days later, in any app, without the app's undo history. Re-selecting the pasted text automatically (Shift+Left n times) was turned down: Word, Notion and Logseq change pasted text and count characters differently. |
| R11 | Interface | One bar window holding both buttons, keeping its right edge when a button is hidden or shown; a shared bubble; a History window that takes the focus, with a word diff; one activity at a time (dictation or refine); Esc taken from other apps only while the model works | The mic must not move when the pencil appears. |
| R12 | Settings | A `refine:` section (hotkey, default, model, button, max_chars, timeout_s, prompts); a tray group; showing or hiding the pencil applies at once, a hotkey change restarts the app | Same pattern as `dictation:`. |

## Measurements (the reference machine, 2026-11-07)

The owner's tray had stopped its services that evening, so the tests used a private gateway on port 4010 with this
branch's config and a second copy of the app on port 8791 with test hotkeys; qwen3.5:9b in Ollama.

- Prompt probes: 7 styles x 4 samples (an e-mail with typos, a question with a request, a Logseq line with `[[link]]`,
  `#tag`, `((block ref))` and `key:: value`, two lines with Windows line breaks): 0.6-2.1 s each. The question stayed a
  question in every style; the Logseq markup and the line breaks were kept.
- Found and fixed by those probes: Friendly rewrote "This are the first paragraph" as "Here's the first paragraph.",
  which the first answer check rejected; Professional added "Best regards," with nothing after it (rule added: no
  greeting, sign-off or placeholder the text does not have); one reply ended in `"}`. Still seen: the 9B sometimes
  leaves a typo in Bullet points or a lowercase sentence start in Fix spelling and grammar only.
- End to end in a Win32 EDIT control (15 checks): refine over the control endpoint, through the injected hotkey and
  through a real mouse click on the pencil (the target kept the focus and its selection); 1.9-2.3 s from trigger to the
  replaced text; Windows line breaks kept; the clipboard was back to its earlier content after every step; revert
  restored the original exactly; "nothing selected" changed nothing and logged nothing.
- Word (a new document over COM, closed without saving): two paragraphs refined in place (still two paragraphs) and
  reverted to the exact original.
- Edge (`--app` window, its own profile folder): a textarea and a contenteditable div refined in place and reverted;
  clipboard restored.
- An independent code review (a code-review agent) found, before the first commit: the refine button's menu called methods the app does not have, and the new RefineUI class had been inserted inside App, taking the mic menu's Paste last text again and Copy last text with it (both would have failed on the first right-click); Esc during a refine unregistered itself on the hotkey thread and froze every hotkey for 3 s; Esc could stay taken from other apps after a badly timed cancel; replace() could pull the focus back from an app you had moved to; a ``` block in the text broke the reply parser; the answer check rejected fixes such as "sorry i cant come" to "Sorry, I can't come."; Ctrl+C in an editor's terminal panel. All were fixed; a test now reads overlay.py and history.py and fails when they call a name the App class lacks. After the fixes, the live checks above passed again in the EDIT control (15), Esc cancelled a 1,500-character refine in 0.3 s with nothing replaced (6), both right-click menus opened for real and Refine history... opened the history window from the menu (7), and Ctrl+Insert copied from a real EDIT control. The Word and Edge runs were not repeated after the fixes (the session's permission check refused the rerun).
- Hiding the pencil kept the mic where it was (bar 92x44 at x 1800 became 44x44 at x 1848); hiding both withdrew the
  window; showing them restored it. The History window listed the test log with the word diff and handed Copy and
  Revert to the app.

## Not verified

- Logseq and Notion themselves (the owner's notes are in them); their kind of text field was tested in Edge.
- Word's own Ctrl+Z after a refine; formatting inside a selection in Word (bold, links) after a refine.
- The bar's and History window's look (no screen capture), the right-click menu clicked by hand, the tray's new
  settings group in the live tray, "Add or edit styles..." opening an editor.
- Long selections (the tests used under 250 characters) and languages other than English.

## Follow-ups worth considering

- A Logseq plugin with a "Refine" item in the block context menu (`logseq.Editor.registerBlockContextMenuItem`), which
  would also refine whole blocks without selecting their text.
- A "show me first" option: the suggestion in the bubble with Replace and Keep buttons.
- Streaming the reply into the bubble for long selections.
