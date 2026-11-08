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
| A11 | GPU or CPU (asked 2026-11-08) | `read_aloud.device` auto, gpu or cpu. GPU through onnxruntime-gpu 1.31.1 (CUDA 13) with cuDNN 9.28 for CUDA 13 (`nvidia-cudnn-cu13`, installed without dependencies) and the CUDA 13 runtime and cuBLAS that Ollama ships in `lib/ollama/cuda_v13`; onnxruntime-gpu replaces onnxruntime in voice typing's environment (it includes the CPU provider, and the VAD asks for the CPU). Installed by `read-aloud install` for gpu, or auto on an NVIDIA PC (about 0.8 GB). fp32 only on the GPU. A failed GPU run (out of memory) moves Kokoro to the CPU until voice typing restarts | DirectML (any GPU, one 20 MB wheel) failed on Kokoro's ConvTranspose layers ("The parameter is incorrect"). onnxruntime-gpu's own dependency tree would add cuBLAS 13 again (0.64 GB) that Ollama already ships. int8 on CUDA ran 5-6x real time, slower than fp32 (12-20x). |
| A12 | Less waiting (asked 2026-11-08) | Sentence-sized pieces (first up to 120 characters, later up to 160, joining short sentences), so no piece takes long to make; the first is made alone, then later pieces by worker threads (two on the CPU sharing Kokoro's six threads, one on the GPU) and handed to the player in order, up to 30 s of speech ahead on the CPU and 60 s on the GPU. While the processors are more than 85% busy (GetSystemTimes), one at a time and one ahead. Kokoro loads while the selection is copied, and when the pointer rests on the speaker button | Pieces of up to 320 characters made one at a time left a 3-4 s silence after the first sentence on the CPU. Two sessions for two workers would double the memory; two concurrent runs on one session (4.3x real time against 3.3x) use no more threads. Three runs (5.0x) would take the processors from other programs. |
| A13 | Read it again (asked 2026-11-08) | The last reading's audio stays in memory (up to 64 MB, about 23 minutes) keyed by its text, voice, speed and weights; Read it again replays it and makes only pieces that are missing (a reading stopped partway). A replay writes no usage record. Never on disk | Re-running the model for the same text was wasted work. |
| A14 | The tray's Kokoro row (asked 2026-11-08) | While the standalone Kokoro service is off, the Kokoro row shows read aloud (from voice typing's /health): off, not installed, starts with voice typing, ready, loaded on the GPU or CPU, reading, paused, failed; it carries Hide/Show speaker and has no Start button | The row said "Not available yet" while read aloud was using Kokoro. |

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

- GPU (2026-11-08, throwaway venv with onnxruntime-gpu 1.31.1, cuDNN 9.28.1.4 for CUDA 13, Ollama's cuda_v13): 18.6 s
  of speech in 0.86 s (fp32, warm), 0.3-0.4 s per sentence, the first of a new length up to 0.7 s; 1.0 GB of GPU
  memory (9.0 of 12 GB on the card with the 9B and Whisper loaded). The parallel reader on the GPU: first speech
  0.85 s after the request with Kokoro loaded, no waiting between the 7 pieces of a 751-character text (47 s of speech
  made in 3.3 s); Read it again started at once and made nothing. The same on the CPU (two workers, Kokoro loaded
  first): first speech after 1.74 s, again no waiting between pieces.
- CPU parallelism (12 logical processors): one run at a time with 6 threads 3.3x real time, with 3 threads 2.2x; two
  runs at once sharing 6 threads 4.3x, three 5.0x; two runs on 3 threads each 3.5x.

## Not verified

- Hearing it: no audio was played through the speakers (the live checks wrote WAV files or played silence).
- The owner's installed voice typing app with read aloud: `stack.py read-aloud install` was not run against
  `C:\media\dictation` (it changes the live environment); the tray's new group and buttons were not seen in the live
  tray; the installer's new row was checked in a hidden window only.
- Capturing a real selection with the speaker button or Ctrl+Alt+S (the capture is refine's, live-tested on
  2026-11-07; read aloud only adds the purpose flag); reading in Word, Logseq, Notion and browsers.
- Languages other than English through Kokoro (French, Spanish, Hindi, Italian, Portuguese were phonemized, not
  listened to).
