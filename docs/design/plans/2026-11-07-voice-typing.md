# Voice typing in every app

Date: 2026-11-07. Status: built on branch `claude/whisper-speech-to-text-extension-99ad1f`; verified on SEKAIHOME
with recorded speech (details below); not yet used with a live microphone.
Manual: [user-guide.md, "Voice typing"](../../manuals/user-guide.md#voice-typing). Code: `scripts/stacklib/dictation/`.

## Ask

The owner wants to speak instead of type into text fields, documents and Logseq, with Whisper running locally: a
button, a hotkey, an automatic stop after a quiet period, and either text as you speak or text after you finish,
cleaned up (fillers removed, sentences shortened) the way Pixel's AI keyboard does it.

## Decisions

| # | Question | Choice | Why; what was turned down |
|---|---|---|---|
| V1 | Where it lives | A Windows desktop app run as a stack service (`dictation`), started by the tray | A browser extension cannot reach Logseq desktop or Word; a Logseq plugin covers one app. The multimodal plan's Open WebUI microphone (D-M4) stays as it is for in-chat dictation. |
| V2 | Speech to text | faster-whisper `large-v3-turbo`, int8_float16 on the GPU; `small` int8 on the CPU when the GPU is not usable | Measured below. whisper.cpp's prebuilt binaries are unsigned executables (Smart App Control risk); Open WebUI's built-in Whisper runs on the CPU and needs a login. |
| V3 | Python environment | Its own venv under `<media.root>\dictation`, from python.org Python 3.14, pinned versions that loaded under Smart App Control | Keeps CTranslate2, onnxruntime and PyAV out of the project venv (`uv sync` is exact and would remove an optional extra). Same pattern as ComfyUI. |
| V4 | CUDA libraries | Borrow `cublas64_12.dll` from Ollama's `lib\ollama\cuda_v12` (NVIDIA-signed); fall back to `nvidia-cublas-cu12` | CTranslate2's Windows wheel ships cuDNN but not cuBLAS. Every machine of this stack has Ollama; the wheel is 0.5 GB. |
| V5 | Microphone | WinMM (`winmm.dll`) through ctypes, opened only while recording | Nothing compiled for Smart App Control to refuse; sounddevice and PyAudio carry unsigned PortAudio DLLs. An always-open microphone was rejected (the Windows microphone indicator would never go off). |
| V6 | Silence and phrases | Silero VAD, the ONNX model faster-whisper ships, run one 32 ms frame at a time with carried LSTM state; an energy detector if it cannot load | Robust to steady noise; well under 1 ms per frame on one thread. |
| V7 | Real time versus after | One pipeline: each phrase is transcribed when you pause (prompted with the text so far). Live mode types it at once; polish mode joins the phrases and sends them to the cleanup when you stop | The wait after you stop is one short phrase plus the cleanup, not the whole recording. Re-transcribing a growing buffer and backspacing corrections was rejected: no app's text can be revised safely from outside. |
| V8 | Cleanup | Gateway alias `local-small` (private), JSON mode, `think: false`, temperature 0.2; the reply is rejected when it grew, shrank too much or reads like an answer | JSON mode keeps the gateway's model label off the text; thinking made the 9B return nothing (below). On rejection or a gateway failure the transcript is typed with filler sounds removed by rule. |
| V9 | Getting text into the app | Paste (save clipboard, Ctrl+V, restore after 1 s unless it changed; hidden from clipboard history) by default; typed Unicode keystrokes as an option. Each clipboard operation uses its own owner window, destroyed right after | Paste is fast for long text and every script; typing suits apps that block paste. Text never goes into a window other than the one that had focus at the start, nor into one that may run as administrator, nor while Ctrl or Alt is still held; it goes to the clipboard instead. A long-lived owner window on a thread without a message loop could stall other programs' copy (WM_DESTROYCLIPBOARD is sent synchronously). |
| V10 | Hotkey | Ctrl+Alt+D; tap to talk until quiet, hold to talk while held; Esc cancels | Ctrl+Alt+Space is registered by the Claude desktop app here (RegisterHotKey error 1409); Ctrl+Shift+Space is parameter hints in VS Code. |
| V11 | Button | 44 px Tk window, `WS_EX_NOACTIVATE` and topmost, Windows 11 rounded corners; bubble above it with the live transcript | A click must not move the keyboard focus away from the app being dictated into. |
| V12 | Control | `127.0.0.1:8790` `/health` (tray status) and POST actions; refuses requests with an Origin header or a foreign Host | Stops web pages from starting the microphone by cross-site requests or DNS rebinding. The bind is also the single-instance lock (no SO_REUSEADDR on Windows). |
| V13 | Privacy | Audio only in memory; logs carry lengths and timings, not words; the cached model loads with `local_files_only` | faster-whisper otherwise asks huggingface.co for a newer revision on every load. |

## Measurements (SEKAIHOME, 2026-11-07)

- large-v3-turbo on the RTX 3060 with qwen3.5:9b resident: load 5-8 s from the USB SSD; 3.5 s of speech in 0.30 s,
  15 s in 0.6 s (warm); VRAM 7977 -> 9174 MiB (about 1.2 GB).
- The same model on the Ryzen 5 5500 (int8): 9.7 s for 15 s of speech, hence `cpu_model: small`.
- Cleanup through `local-small`: 0.55-1.2 s. Without `think: false` the 9B spent the 400-token cap on reasoning and
  returned empty content after 49 s.
- Synthetic dictation (Windows TTS, 3 phrases, fillers and a self-correction, then 4.5 s of silence and a sentence that
  must not appear): phrases split at the pauses, silence stop 3 s after the last phrase, Whisper 0.29-0.52 s per
  phrase, cleanup 1.18 s. "Thursday, no wait, Friday" became "Friday"; the question stayed a question.
- End to end through the running app with a replayed recording (`AGENT_STACK_DICTATION_TEST_WAV`) into a test window:
  polish mode pasted "Please add milk and eggs to the shopping list." 1.1 s after the automatic stop and restored the
  clipboard; live mode typed three phrases as keystrokes with correct spacing; cancel typed nothing; a second copy of
  the app exited ("already running"); hold-to-talk with Ctrl+Alt+D held through SendInput typed nothing while held and
  all three live phrases at the release.
- An independent code review found eight defects (elevation check, keys still held, live-mode outcome read too early,
  "paste last" target, cleanup after an error, a stale tray profile, the clipboard restore delay, no watchdog for an
  unplugged microphone) and the clipboard-owner risk in V9; all were fixed before the first commit.

## Not verified

- A live microphone and a person speaking (the tests replayed recordings); the hotkey pressed by hand (hold-to-talk
  was driven by injected key events); the bubble's look (a screen capture was refused); an unplugged microphone.
- Pasting into Logseq, Word and Notion themselves (the test window was a Tk text box).
- Thai dictation and the cleanup prompt on Thai text.
- The tray's new row, settings group and menu item in the live tray (it runs the old code until restarted from the main
  checkout); Linux and macOS (the recorder falls back to sounddevice, but hotkeys and input are Windows only).

## Follow-ups worth considering

- An OpenAI-compatible `/v1/audio/transcriptions` on the same process, so Open WebUI's microphone could use the GPU
  model instead of its CPU Whisper (would revisit D-M4).
- A "bullets" style for Logseq (one block per sentence).
