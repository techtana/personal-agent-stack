# Read selected text aloud in every app

Date: 2026-11-08. Status: built on branch `claude/read-aloud-highlighted-text-57ce4d`; verified on the reference
machine with a test copy of the voice typing app (details below); not yet installed into the owner's voice typing
environment, and not yet heard through the speakers by the owner.
Manual: [user-guide.md, "Read aloud"](../../manuals/user-guide.md#read-aloud). Code: `scripts/stacklib/dictation/`
(`speak.py`, `espeak.py`, `tts.py`, `player.py`, `reader.py`, and the read aloud parts of `app.py` and `overlay.py`).

## Ask

The owner asked for another module, in the same manner, settings and interface as voice typing and refine, that reads
highlighted text aloud. Later the same day: the buttons go pencil, mic, speaker from left to right, and read aloud is a
separate optional choice in the installer, handled gracefully when it is not installed.

## Decisions

| # | Question | Choice | Why; what was turned down |
|---|---|---|---|
| A1 | Where it lives | Inside the voice typing app, like refine: its bar, hotkey thread, clipboard thread, control port and tray row | The app already reads selections safely (refine's `selection.capture`) and has a window that never takes the focus. A separate resident app would repeat all of it. |
| A2 | Optional | `read_aloud.enabled` (off by default), set by the installer's **Read aloud (Kokoro)** feature or `stack.py read-aloud install`; the feature `requires` voice typing (ticking it ticks voice typing, unticking voice typing unticks it). Its packages (espeakng-loader, comtypes) go into voice typing's environment only when chosen | The owner asked for a separate install choice. Off: no button, no hotkey, the tray hides its controls. On but missing pieces: the button says what to install; Kokoro missing falls back to a Windows voice; reading never downloads. |
| A3 | Natural voices | Kokoro-82M v1.0 (Apache-2.0) as ONNX (`onnx-community/Kokoro-82M-v1.0-ONNX`, revision pinned), on the CPU through the onnxruntime voice typing already has; espeak-ng 1.52 for phonemes through ctypes (the espeakng-loader wheel's DLL, GPL-3.0, loaded as a separate library) | The multimodal plan's Kokoro-FastAPI service (PyTorch, port 8880, for Open WebUI) is not installed and needs its own Smart App Control spike; the ONNX model needs no PyTorch and no GPU. phonemizer-fork and kokoro-onnx were turned down for their dependency chain (csvw, rdflib, ...) around the same three espeak-ng calls. Japanese and Chinese voices need Kokoro's own G2P (misaki with pyopenjtalk or jieba), so they are not offered. |
| A4 | Instant and other languages | Windows' own voices through SAPI with comtypes (pure Python, `dynamic=True`, no generated modules), OneCore voices included by opening their tokens from the Speech_OneCore registry path; rendered into an SpMemoryStream at 24 kHz 16-bit mono, Kokoro's format | Zero download, any language with a Windows voice. WinRT `Windows.Media.SpeechSynthesis` through ctypes and a PowerShell helper were turned down (much more code; a process start per sentence). |
| A5 | Playback | WinMM `waveOut` through ctypes, two pieces in flight, pause and resume with waveOutPause/Restart, stop within 50 ms; a WAV-file player with the same methods when `AGENT_STACK_READ_TEST_OUT` is set | No compiled package for Smart App Control to refuse, as `audio.py` records with waveIn. |
| A6 | Pieces | Text cleaned for listening (Markdown, Logseq markup, URLs as their host, a full stop at the end of every line), split into sentences (not after abbreviations or initials); the first piece is one sentence of at most 180 characters, later ones join sentences up to 320; no piece crosses a paragraph; at most 8 s of speech prepared ahead | The voice starts in under a second warm; a stop wastes at most one piece of work. 20 s ahead (the first try) had made 24.6 s of speech for a reading stopped after 2 s. |
| A7 | Languages | `auto_language`: the writing system decides first (Thai, Devanagari, Cyrillic, kana, Han, ...); Latin text by common short words and marked letters, only when it is clear (at least 4 words and a margin); then `read_aloud.voices`, Kokoro's voice for that language, or an installed Windows voice; otherwise the chosen voice reads it and the bubble says how to add one | A short Latin-script phrase cannot be told apart reliably, so it keeps the chosen voice. |
| A8 | Controls | Hotkey Ctrl+Alt+S (free on the reference machine by RegisterHotKey probe) toggles; a click stops, or resumes a pause; Esc stops while it reads (`esc_stops`); right-click menu: pause, read it again, voice (search picker with a sample), speed, the language switch, hide | Same shape as refine. Esc is taken from other apps only during a reading. |
| A9 | With dictation | Starting to dictate stops a reading; a reading waits while you dictate | The microphone would hear the voice. |
| A10 | Records | One usage record per reading (source `read-aloud`, kind `speech`): seconds of speech, the time the voice worked, load time, phoneme tokens, voice, language, speed, whether it was stopped; the wall clock ends when the last piece is made, not when playback ends. Nothing about the text, and nothing on disk but that | The Usage tab already shows speech rows in seconds and times real time (AGENTS.md rule 11). |

## Measurements (the reference machine, 2026-11-08)

- Smart App Control on: espeak-ng.dll from espeakng-loader 0.2.4 loaded; onnxruntime 1.31.1 was already trusted in
  voice typing's environment.
- Kokoro on the CPU (6 of 12 threads, `allow_spinning` off): load 1.2-2.3 s; 43 tokens (3 s of speech) in 0.8 s, 298
  tokens (17 s) in 5.8-6.1 s, the same for fp32 (326 MB), fp16 (163 MB) and int8 (92 MB). Working set after a
  sentence: +0.50 GB with fp32, +0.31 GB with int8. A whole test text: 17.6 s of speech in 5.0 s (3.5x real time).
- Windows voices: 6 s of speech in 0.02-0.05 s; David, Zira and Mark (OneCore) and David and Zira Desktop (SAPI) on
  this English Windows; OneCore David renders byte for byte as David Desktop.
- Whisper (small, CPU) transcribed Kokoro's fp32 and int8 output, the cleaned Markdown test text and a Zira sample
  back word for word ("github.com" came back as "GitHub, Calm").
- A test copy of the app on port 8797 (Whisper not loaded, sound into a WAV file, nothing saved to the machine file):
  first speech 2.1 s after the request including Kokoro's load; bubble "Reading with Heart (1 of 2)"; pause, resume
  and stop over the control port; a voice chosen from the menu played its sample and was saved; hide and show from
  the tray's side; three usage records.
- WinMM player with silence (inaudible): three 0.5 s pieces started 0.5 s apart and ended after 1.56 s; stop took
  11 ms.

## Not verified

- Hearing it: no audio was played through the speakers (the live checks wrote WAV files or played silence).
- The owner's installed voice typing app with read aloud: `stack.py read-aloud install` was not run against
  `C:\media\dictation` (it changes the live environment); the tray's new group and buttons were not seen in the live
  tray; the installer's new row was checked in a hidden window only.
- Capturing a real selection with the speaker button or Ctrl+Alt+S (the capture is refine's, live-tested on
  2026-11-07; read aloud only adds the purpose flag); reading in Word, Logseq, Notion and browsers.
- Languages other than English through Kokoro (French, Spanish, Hindi, Italian, Portuguese were phonemized, not
  listened to).
