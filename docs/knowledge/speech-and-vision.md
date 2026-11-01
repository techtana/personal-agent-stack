# Speech and vision: talking to the stack and showing it pictures

## What this is and why the project needs it

The owner wants to dictate instead of type, hear answers read aloud, and show the model a photo, a diagram or a
painting. These are three separate jobs: **speech to text** (STT), **text to speech** (TTS) and **vision** (reading
images). None of them needs the big GPU on SEKAIHOME: speech runs well on the CPU, and the chat model already accepts
images. This page explains how each works, what it costs, and the privacy points. Plan packages M1 (vision) and M2
(speech) build on it.

## The ideas, built up from zero

### Speech to text

An STT model listens to audio and writes the words. **Whisper** (OpenAI, MIT licence) is the common open choice. It
comes in sizes from `tiny` to `large`; `base` and `small` run comfortably on a CPU for dictation. **faster-whisper**
is a re-implementation on the CTranslate2 engine that is faster and uses less memory on the CPU.

Open WebUI has a local Whisper built in, so dictation needs no new service: the microphone button records in the
browser, Open WebUI transcribes on the server, and the text lands in the input box. The model size is a setting.

### Text to speech

A TTS model turns text into a voice. **Kokoro** (82 million parameters, Apache-2.0 weights) gives natural voices and
is small enough for the CPU. **Kokoro-FastAPI** wraps it in a server with an OpenAI-compatible endpoint
(`/v1/audio/speech`), so any client that can talk to OpenAI's speech API can use it by changing the base URL. It
starts natively with uv (`start-cpu.ps1` on Windows), serves on port 8880, and offers several voices that can be
blended (`af_sky+af_bella`).

Open WebUI's TTS setting points at that endpoint: engine `openai`, base URL `http://127.0.0.1:8880/v1`, model
`kokoro`, a default voice.

### The OpenAI audio endpoints, and why the gateway can carry them

Both jobs have standard HTTP shapes: `POST /v1/audio/transcriptions` (send audio, get text) and
`POST /v1/audio/speech` (send text, get audio). LiteLLM proxies both. So the stack can either let Open WebUI talk to
Whisper and Kokoro directly, or route speech through the gateway so traces and the tray's Usage tab count it
(decision D-M4).

### Vision-language models

A vision-language model (VLM) reads images as well as text. An image encoder cuts the picture into patches and turns
them into tokens; the language model then reads those tokens with the text. Two consequences:

- **Images cost context.** A picture becomes hundreds to a few thousand tokens depending on its resolution. A large
  screenshot can fill a good share of a 32k context. Resize big images before sending them.
- **No second model needed, if the chat model is a VLM.** The Qwen 3.5 family accepts images in all sizes, the 9B
  included. If Ollama's `qwen3.5:9b` lists the `vision` capability (`ollama show qwen3.5:9b`), the stack gets image
  recognition with no extra memory and no reload. A separate VL model would cost a reload of a minute or more on
  this machine each time chat and vision switch.

For a request with an image to reach the model, two switches must be on: the gateway deployment must say
`supports_vision: true`, and the Open WebUI model must have the `vision` capability. Both are `False` today
(`scripts/stacklib/litellm_build.py`, `scripts/stacklib/agents_build.py`).

### Privacy

A voice is biometric data: it identifies a person ([privacy-for-llm-systems.md](privacy-for-llm-systems.md)). Here
it never leaves the machine, but Open WebUI may keep uploaded audio files in its data folder. Check where and for how
long, and say so in the user guide. Photos can carry faces and location metadata (EXIF); the same rule applies.

## Rules of thumb and typical numbers

- Dictation: Whisper `small` on the CPU is a good default; `base` if the CPU is busy.
- TTS: Kokoro on the CPU; no GPU needed.
- Vision: use the chat model's own vision; resize images to about 1-2 megapixels first.
- Turn on vision in both places (gateway and Open WebUI), or images are silently dropped or refused.

## Common misconceptions and edge cases

- **"Vision needs a separate model."** Not with Qwen 3.5: the chat model reads images itself.
- **"Speech needs the GPU."** Not for dictation or a natural voice at this size.
- **"Setting an env variable changes Open WebUI."** Open WebUI keeps saved admin settings in its database, and those
  override env values. Check the effective setting in the admin panel or through its API.
- **"Local speech is private, so nothing to think about."** Stored recordings and photos are still personal data on
  disk.

## How the project uses it

- M1: `vision: true` on `qwen3.5:9b` in `machines/_defaults.yaml`; the build sets `supports_vision` from it; agent
  YAMLs gain `capabilities: {vision: true}`. Smoke test: send a small PNG and check the answer.
- M2: Whisper settings in the Open WebUI env; Kokoro-FastAPI as a native service `kokoro` on port 8880, off by
  default, with a tray entry. Smoke test: speak a sentence with Kokoro, transcribe it with Whisper, compare the words.

## What we found

Not measured here yet. Smart App Control may block Kokoro's compiled modules; spike S0d checks that first.

## Open questions

- Does `ollama show qwen3.5:9b` list `vision` for the tag pulled on SEKAIHOME?
- What are the exact audio setting names in the installed Open WebUI 0.12.3?
- Where does Open WebUI store recorded audio, and can retention be limited?

## Sources and further reading

| Source | Author / year | Good for |
|---|---|---|
| [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) | remsky, 2026 | native start scripts, endpoint, licence |
| [Qwen 3.5 on Ollama](https://summarizemeeting.com/en/news/ollama-qwen-3-5-local-tool-calling-multimodal) | 2026 | image support in all sizes |
| [LiteLLM proxy endpoints](https://docs.litellm.ai/docs/providers/litellm_proxy) | LiteLLM, 2026 | audio endpoints through the gateway |
| [Open WebUI media docs (summary)](https://deepwiki.com/open-webui/docs/3.5-media-generation) | DeepWiki, 2026 | STT and TTS engines, image backends |

## Changes

- 2026-11-01: first version.
