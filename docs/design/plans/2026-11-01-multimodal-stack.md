**Status:** proposed 2026-11-01. Nothing is built. The decisions in section 12 are open. The next session starts from
[../../HANDOFF-2026-11-01-multimodal.md](../../HANDOFF-2026-11-01-multimodal.md).

# Multimodal stack: vision, speech, images, video with audio, music and routing per message

## 1. Goal

The owner wants one private stack that does all of this on SEKAIHOME:

- writing, coding, software architecture, science and art critique;
- image recognition, so the model can read a photo, a diagram or a painting;
- web search;
- image generation, image editing and style transfer;
- **video generation with audio**: sound effects in time with the picture, plus optional narration and music;
- music generation;
- speech in (dictation) and speech out (read the answer aloud);
- a router that picks the right "expert" for each message, so the owner does not pick a model by hand.

Every feature runs on the owner's own hardware. That is the private-first rule (AGENTS.md rule 9).

## 2. Where the repository stands (2026-11-01)

| Capability | State | Evidence |
|---|---|---|
| Routing | A different kind exists. Each department is a LiteLLM `complexity_router`. It picks a tier by difficulty, not by subject or media. All tiers resolve to `qwen3.5:9b`. | `scripts/stacklib/litellm_build.py`; README "Known issues": "A chat message cannot switch models" |
| Vision | Planned, not built. Plan B sends media to "a local vision model", chosen later (B-D3). | `supports_vision: False` in `litellm_build.py` (`LOCAL_INFO`); `"vision": False` in `agents_build.py` (`build_openwebui_model`) |
| Image generation, web search | Off on purpose. The installer is to turn them off. | `docs/plans/SHARED-COMPONENTS.md` S4 |
| Speech, video, music, style transfer | Not planned. ffmpeg and whisper.cpp appear only as privacy-gate scanners. | `SHARED-COMPONENTS.md` S1b; `winget_build.py` |
| Departments | Six, all for software work. Nothing for writing, science or art. | `agents/*.yaml` |

## 3. Constraints

| # | Constraint | Consequence |
|---|---|---|
| C1 | One RTX 3060 with 12 GB. The 9B holds 6.2 GB of model weights at 32k (8.0 GB on the card in total, measured at 16k) and stays loaded (`keep_alive: -1`). The FIM model keeps another 1.3 GB. Image models need about 9-11 GB on this card (FLUX or SDXL at int8). | One large GPU model at a time. Chat and media must hand over the GPU (section 7). |
| C2 | A cold load of the 9B from the USB SSD took 130-161 s (`memory/state.md`). | Many separate "expert" LLMs would mean minutes of waiting at each switch. The experts are prompts on one shared model (section 8). |
| C3 | Smart App Control blocks unsigned compiled modules file by file. It broke Phoenix (`memory/lessons.md`, 2026-10-26). | Each new PyTorch service (ComfyUI, Kokoro, custom nodes) must pass a spike before anything depends on it. |
| C4 | 32 GB DDR4. The usual desktop load leaves about 11-12 GB free. Wan 2.2 with offload wants 24-32 GB of system RAM. | Video runs with desktop apps closed, or not at all. Keep the 9B as primary; the 35B MoE leaves no RAM for media. |
| C5 | C: has about 36 GB free. The media models in section 5 add roughly 40-60 GB. The model drive is the owner's choice. **Agent sessions never read, write or stage anything on D: or in OneDrive.** | The owner sets model paths in `machines/SEKAIHOME.yaml` and copies model files himself. The build reads the paths; agents do not touch those folders. |
| C6 | Native services only, no Docker or WSL2 (ADR 2026-10-24). | Each service runs as a uv environment or a vendor installer, managed by `stack.py` and the tray. |
| C7 | Licences must be checked before a model is named (lesson 2026-10-26). | Section 5 lists each licence. Non-commercial weights need an owner decision (D-M3). |
| C8 | Ollama's image generation runs on macOS and Linux with CUDA only. | Images come from ComfyUI on this Windows machine. |
| C9 | The repository is public. | No personal data, paths under the user profile or file names from personal folders in commits. |

## 4. Target architecture

```
Open WebUI :3000  (owner's surface)
 |
 |-- chat ----> "Auto" pipe function ----> LiteLLM :4000 ----------------> Ollama :11434
 |              picks a department          department routers             qwen3.5:9b (text + vision)
 |              per chat                    (coding + writer, scientist,   one runner shared by all aliases
 |                                           architect, art-critic)        qwen2.5-coder:1.5b (FIM)
 |
 |-- mic ------> Whisper inside Open WebUI (CPU)
 |-- speaker --> Kokoro-FastAPI :8880 (CPU, OpenAI /v1/audio/speech)
 |-- image ----> ComfyUI :8188 (GPU)   Z-Image-Turbo / FLUX schnell; SDXL + IP-Adapter for style
 |
 +-- (v2) "make video" tool --> ComfyUI queue

ComfyUI UI :8188  (batch jobs, minutes each)
   video with audio:  Wan 2.2 TI2V-5B --> video-to-audio (Foley) --> + Kokoro narration --> + ACE-Step music
                      --> ffmpeg mix and mux --> MP4 with an AAC track
   music:             ACE-Step 1.5

Tray "GPU mode": Chat (Ollama owns the GPU)  <->  Media (Ollama unloaded, ComfyUI owns the GPU)
```

## 5. Components and model choices

All facts below are from web sources read on 2026-11-01. They are medium confidence until the spike (section 10)
measures them on SEKAIHOME.

| Capability | Component | Model and licence | GPU memory | Notes |
|---|---|---|---|---|
| Writing, coding, science, architecture, art critique | Ollama via LiteLLM | `qwen3.5:9b` (already pulled) | ~8 GB at 32k | New departments are prompts on the same runner (section 8). |
| Image recognition | Ollama via LiteLLM | `qwen3.5:9b`: the Qwen 3.5 family accepts images, 9B included | none extra | Confirm with `ollama show qwen3.5:9b` (look for `vision`). Fallback: a separate VL model that swaps in (reload cost, C2). |
| Speech to text | Open WebUI built-in Whisper (faster-whisper) | Whisper `small` or `base` (MIT) | CPU | No new service. Check the env names against the installed 0.12.3. |
| Text to speech | Kokoro-FastAPI, native uv start script (`start-cpu.ps1`) | Kokoro-82M (Apache-2.0); wrapper Apache-2.0 | CPU | OpenAI-compatible at `http://127.0.0.1:8880/v1`, model `kokoro`. |
| Image generation | ComfyUI | Z-Image-Turbo 6B (Apache-2.0) as default; FLUX.1 schnell (Apache-2.0) as alternative; FLUX.2 klein 4B (Apache-2.0). FLUX.2 klein 9B is non-commercial. | ~9-11 GB | Reported on a 3060: FLUX schnell int8 at 1024 px in 3-5 s, SDXL in 8-12 s. |
| Image editing, style transfer | ComfyUI | SDXL (CreativeML OpenRAIL++-M) + IP-Adapter (Apache-2.0); an edit model (FLUX.2 klein edit or a quantised Qwen-Image-Edit) if one fits | ~9-11 GB | Pick the edit model in spike S0b by fit and quality. |
| Video | ComfyUI | Wan 2.2 TI2V-5B, fp8 (Apache-2.0) | 12 GB with `--lowvram`; 24-32 GB system RAM | Reported 5-12 min for a short 720p clip on 3060-class cards. 720p, 24 fps, up to 5 s. |
| Sound for video (Foley) | ComfyUI custom node | HunyuanVideo-Foley (Tencent's own licence, not OSI; read its territory and use terms before adopting it) **or** MMAudio large 44k v2 (weights CC BY-NC 4.0, non-commercial) | Foley fp8: under 8 GB; with block swap under 4 GB | Chosen in spike S0e (D-M2). |
| Narration for video | Kokoro-FastAPI | Kokoro-82M (Apache-2.0) | CPU | Same server as text to speech. |
| Music | ComfyUI (native template) | ACE-Step 1.5, released 2026-02-03 (MIT) | under 4 GB reported | Reported under 10 s per song on an RTX 3090; expect slower on a 3060. |
| Mix and mux | ffmpeg (already in `winget/configuration.winget`) | - | CPU | `loudnorm`, `sidechaincompress` for ducking, AAC into MP4. |
| Web search | Open WebUI web search | decision D-M5 | - | Queries leave the machine whatever engine is used. |
| Routing | Open WebUI pipe function | uses `local-small` (same runner) | none extra | Section 8. |

## 6. Video with audio

The owner requires audio on generated videos. Two routes exist.

### Route A (default): a composed pipeline in one ComfyUI workflow

Each stage loads its model, runs, and lets ComfyUI unload it before the next stage. Only one large model is on the
GPU at a time.

| Step | What | Model | Output |
|---|---|---|---|
| A1 | Generate the picture from text, or from a start image | Wan 2.2 TI2V-5B fp8 | frames, 720p, 24 fps, up to 5 s |
| A2 | Generate sound effects and ambience that match the frames | Foley model (D-M2) | WAV, clip length |
| A3 | Optional: speak a narration script | Kokoro | WAV |
| A4 | Optional: generate a music bed of the clip's length | ACE-Step 1.5 | WAV |
| A5 | Mix: Foley at full level, music ducked under speech, loudness normalised; mux into the video | ffmpeg | MP4 (H.264 + AAC) |

Mixing targets, to confirm with the owner: integrated loudness -16 LUFS, true peak at most -1.5 dBTP, music
ducked by about 10 dB under narration.

Where A5 lives: a small module `scripts/stacklib/media_mux.py` with unit tests, called as
`uv run scripts/stack.py media mux --video v.mp4 --foley f.wav [--voice n.wav] [--music m.wav] --out out.mp4`. A
ComfyUI "Video Combine" node can mux a single track, but the mixing rules are easier to test in Python.

Lip-sync (a speaking face that matches the narration) is out of scope for v1. Wan 2.2 S2V is the candidate for a
later package.

### Route B (spike only): one model makes picture and sound together

LTX-2.x generates video and synchronised audio in one pass. LTX-2.5 (released 2026-08-11) is a 22B model. Its
smallest community GGUF (Q3_K_S) is 12.6 GB, larger than this card. The vendor asks for 32 GB of VRAM, and a guide
calls 12-16 GB setups "a demo, not a workflow". Licence: the LTX-2 community licence, royalty-free for entities
under $10M revenue; the weights are gated on Hugging Face.

Decision rule (D-M1): try one 5 s clip, time-boxed to one hour of setup. Adopt Route B only if it finishes in under
20 minutes and the owner prefers its output to Route A's. Otherwise record the result and keep Route A.

### How the owner starts a video

- v1: from ComfyUI's own UI, with the workflow saved in the repo (`config/comfyui/workflows/video_with_audio.json`).
  A chat request would time out: a clip takes minutes.
- v2 (package M5b): an Open WebUI tool `make_video` that queues the same workflow through ComfyUI's API, reports
  progress with status events, and returns a link when the file is ready.

### Acceptance (Route A)

- One prompt produces a 5 s 720p MP4 with an audible, synchronised Foley track, in under 20 minutes on SEKAIHOME
  (target; record the real time).
- With narration and music turned on, speech stays intelligible over the music, and the file measures -16 LUFS +/-
  1 LU (`ffmpeg -af loudnorm=print_format=json`).
- No step needs Docker, WSL2 or a cloud API.

## 7. Sharing the GPU between chat and media

The 9B stays loaded for chat; image and video models need almost the whole card (C1). Options:

| Option | How | Trade-off |
|---|---|---|
| G1 (default) | A tray **GPU mode** switch. *Media*: unload every Ollama model (`POST /api/generate {"model": m, "keep_alive": 0}` for each model in `/api/ps`), then start ComfyUI. *Chat*: ask ComfyUI to free memory (`POST /free {"unload_models": true, "free_memory": true}`), stop it, and let the next chat reload the 9B. | Explicit and simple for one user. The first chat after media pays a reload (measure it in S0c). |
| G2 (safety net, always on) | Start ComfyUI with `--lowvram --reserve-vram 1.0` | An image request while the 9B is loaded still works, more slowly, by offloading to RAM. |
| G3 | Automatic: a filter unloads Ollama before each image request | Open WebUI calls the image engine outside the chat-completion filters, so this needs our own image tool. More code; revisit after G1 is in use. |

The tray already restarts Ollama and edits settings (`scripts/stacklib/settings.py`), so G1 is a small addition there.

## 8. Routing: experts and automatic choice per message

### 8.1 Experts are departments, not separate models

On this machine each extra LLM costs a reload (C2). So each expert is a department: a system prompt and evals on the
shared `qwen3.5:9b` runner. Proposed new departments (D-M8):

| id | For | Vision |
|---|---|---|
| `writer` | essays, emails, editing, tone | no |
| `scientist` | science and maths explanations, checking reasoning | yes (plots, figures) |
| `architect` | software architecture, trade-offs, ADRs | yes (diagrams) |
| `art-critic` | evaluating art, photos and designs | yes |

`agents/*.yaml` gains two optional keys:

```yaml
capabilities: {vision: true}          # copied into the Open WebUI model; default false
surfaces: [gateway, openwebui]         # default: all (claude, opencode, openwebui, gateway, evals)
```

`surfaces` keeps non-coding departments out of Claude Code and OpenCode, where they would add noise. Each new
department still gets evals, because the build generates the promptfoo gate from them.

`machines/_defaults.yaml:model_catalog` gains `vision: true` for `qwen3.5:9b`. `litellm_build.py` sets
`supports_vision` from the catalog instead of the hard-coded `False`.

### 8.2 The "Auto" model in Open WebUI

A pipe function `config/openwebui/functions/auto_router.py` appears as one model, "Auto". For each chat it:

1. Applies rules first: an attached image goes to `art-critic` unless the text asks for code; code fences or file
   names go to `app-dev`; "review", "test", "security", "deploy" or "document" go to their departments.
2. If no rule matches, asks `local-small` for one department id, with a JSON schema answer. `local-small` is the
   same runner as the departments, so nothing reloads.
3. Pins the department for the rest of the chat, so answers do not change voice mid-conversation. A message that
   starts with `@<department>` switches it.
4. Forwards the request with Open WebUI's internal `generate_chat_completion` to the department alias. The
   department's own complexity router still picks the tier.
5. Shows "Routed to: Writer" as a status event. It logs the department and the rule that matched, never the
   prompt text (privacy principle 5).
6. For requests to draw or make a video, answers with a pointer to the image button or the ComfyUI workflow (v1).

This fixes the known issue "A chat message cannot switch models" for Open WebUI. Claude Code and OpenCode keep
choosing departments themselves.

Rejected: LiteLLM's semantic auto router (deprecated); squeezing departments into the complexity router's four
tiers; one model per subject (reloads, C2).

## 9. Speech and web search

**Speech to text.** Open WebUI's built-in Whisper on the CPU. Add the audio settings to the `open_webui` env in
`services.py:commands()`. Open WebUI keeps saved admin settings in its database, and they override env values, so
the smoke test must read the effective config back, not trust the env.

**Text to speech.** Kokoro-FastAPI as a new native service `kokoro` on port 8880, started from its uv start script.
Open WebUI: TTS engine `openai`, base URL `http://127.0.0.1:8880/v1`, model `kokoro`, a default voice. Option D-M4:
route speech through LiteLLM's `/v1/audio/speech` and `/v1/audio/transcriptions` so the tray's Usage tab counts it.

A voice is biometric data (`docs/knowledge/privacy-for-llm-systems.md`). It stays local here. Check where Open WebUI
caches uploaded audio, and how long it keeps it.

**Web search.** Off today (S4). Every engine sends queries off the machine. SearXNG needs Docker or WSL2 on Windows,
which C6 rules out. Options for D-M5: keep off (default); DuckDuckGo with no key; a keyed API (Brave, Tavily). If
turned on: a per-chat toggle only, never on by default, and a dated entry in `DECISIONS.md` that names it as an
exception to private first.

## 10. Work packages

Every package is one pull request with a human checkpoint (AGENTS.md rule 5). Sizes: S under a day, M one to
three days, L more.

| # | Package | Size | Depends on | Acceptance |
|---|---|---|---|---|
| M-S0 | Spike on SEKAIHOME, owner present (changes the machine) | M | owner decides D-M6 | Results table in `memory/state.md` for S0a-S0f below |
| M1 | Vision flag, `capabilities`/`surfaces` keys, four new departments with evals | S | S0a | `smoke` sends a small PNG to `art-critic` and gets a description naming its colour; build and tests pass |
| M2 | Speech: Whisper settings, `kokoro` service, tray entry | S | S0d | `smoke --media` speaks a sentence with Kokoro, transcribes it with Whisper and gets the words back |
| M3 | "Auto" pipe function and provisioning | M | M1 | 20 labelled sample prompts route correctly at least 18 times; status event shown; no prompt text in logs |
| M4 | `comfyui` service, Open WebUI image generation with a saved workflow and node map, style-transfer workflow, tray GPU mode | M | S0b, S0c | Image button returns a 1024 px image; switching GPU mode twice leaves no model loaded twice; chat works after media mode |
| M5a | Video with audio, Route A, music workflow, `media_mux.py` with tests | M-L | M4, S0e | Section 6 acceptance |
| M5b | `make_video` tool in Open WebUI | M | M5a | A chat request queues a clip and returns its link with progress shown |
| M6 | Web search | S | D-M5 | Only if the owner turns it on; per-chat toggle; decision recorded |
| M7 | Manuals, README, troubleshooting, `DECISIONS.md`, `memory/state.md` | S | each package | Each package updates its own docs; M7 closes the plan |

### Spike M-S0 checklist

| Check | What to do | Record |
|---|---|---|
| S0a | `ollama show qwen3.5:9b`; send one image through LiteLLM with `supports_vision` on | vision listed?; answer correct? |
| S0b | Install ComfyUI three ways if needed: the Windows desktop installer, the portable build, a uv venv. Keep the first that runs under Smart App Control. Generate a 1024 px Z-Image-Turbo image. | which install works; s per image; peak VRAM |
| S0c | Unload the 9B, run an image, reload the 9B; also run an image with the 9B loaded under `--lowvram` | reload time (warm OS cache); image time both ways |
| S0d | Start Kokoro-FastAPI on the CPU from its uv script | blocked or not; s per sentence |
| S0e | Wan 2.2 5B, one 5 s 720p clip; both Foley candidates on it; ACE-Step 30 s track; desktop apps closed | min per clip; peak RAM and VRAM; which Foley sounds right |
| S0f | Route B: LTX-2.x GGUF, one clip, one hour cap | finished?; time; quality vs Route A |

## 11. Files to change

| File | Change |
|---|---|
| `machines/_defaults.yaml` | ports `comfyui: 8188`, `kokoro: 8880`; `services.comfyui` and `services.kokoro` (`native` or `off`, default `off`); a `media:` section (install dir, models dir, ComfyUI flags); `vision` in `model_catalog` |
| `machines/SEKAIHOME.yaml` | the owner fills in `media:` paths himself (C5) |
| `scripts/stacklib/services.py` | `SERVICE_ORDER`, `commands()`, `health_url()` (ComfyUI `/system_stats`; Kokoro health route to confirm), `EXPECTED_IMAGES`; Open WebUI env for audio and image generation |
| `scripts/stacklib/litellm_build.py` | `supports_vision` from the catalog; optional audio deployments (D-M4) |
| `scripts/stacklib/agents_build.py` | `capabilities` and `surfaces` keys |
| `agents/writer.yaml`, `scientist.yaml`, `architect.yaml`, `art-critic.yaml` | new departments with evals |
| `config/openwebui/functions/auto_router.py` | new pipe function (static asset, not generated) |
| `config/comfyui/workflows/*.json` | API-format workflows: image, style transfer, video with audio, music |
| `scripts/stacklib/settings.py`, `scripts/tray.py` | GPU mode switch; ComfyUI and Kokoro on/off |
| `scripts/stacklib/media_mux.py`, `scripts/stack.py` | `media mux` command |
| `scripts/stacklib/smoke.py` | `--media` checks: vision, TTS to STT round trip, one small image |
| `scripts/stacklib/winget_build.py` | ComfyUI desktop package, if S0b picks it and winget has it |
| `tests/` | services (new commands and health), agents build (`capabilities`, `surfaces`), `media_mux` filter graph |
| docs | README (configuration, commands, known issues), `docs/manuals/*`, `DECISIONS.md`, `memory/state.md` |

Generated files (`config/openwebui/*.json`, `infrastructure/litellm/config.yaml` and the others in AGENTS.md rule 1)
change only through `uv run scripts/stack.py build`.

## 12. Decisions for the owner

| # | Decision | Default proposed |
|---|---|---|
| D-M1 | Video-with-audio route | Route A; try Route B once (S0f) |
| D-M2 | Foley model | Whichever sounds right in S0e, after the licence check in D-M3 |
| D-M3 | Non-commercial or custom-licence weights (MMAudio, FLUX.2 klein 9B, HunyuanVideo-Foley, LTX-2) | Allowed for personal use only, and marked "(NC)" or "(custom licence)" in the model or workflow name |
| D-M4 | Speech through LiteLLM or direct to Kokoro and Whisper | Direct first; through LiteLLM if the Usage tab should count it |
| D-M5 | Web search | Off |
| D-M6 | Where media models live | Owner's choice; the owner copies files and sets the paths |
| D-M7 | GPU sharing | G1 tray switch plus G2 `--lowvram` |
| D-M8 | New departments | `writer`, `scientist`, `architect`, `art-critic` |

## 13. Risks

| Risk | Mitigation |
|---|---|
| Smart App Control blocks PyTorch modules in ComfyUI or Kokoro | Spike first (S0b, S0d); try the signed vendor installer; record the result as a lesson |
| Video jobs page the system (32 GB) | Close desktop apps for video; ComfyUI `--lowvram`; keep the 9B primary, never the MoE, during media work |
| Custom nodes run arbitrary code | Install only the nodes the saved workflows need; pin their commits in the workflow README |
| Licence drift between versions | Record the licence and the version per model in `config/comfyui/MODELS.md` |
| Plan facts are from web pages, not measured here | Spike M-S0 replaces every timing in this plan with a SEKAIHOME measurement |
| Generated media leaves the private boundary through sharing | Outputs stay in the ComfyUI and Open WebUI data folders; nothing uploads automatically |

## 14. Sources (read 2026-11-01)

- Ollama image generation, macOS and Linux CUDA only: https://ollama.com/blog/image-generation (via release notes mirrored at https://gitea.alexlebens.dev/alexlebens/infrastructure/pulls/3436)
- Qwen 3.5 on Ollama accepts images, all sizes including 9B: https://summarizemeeting.com/en/news/ollama-qwen-3-5-local-tool-calling-multimodal
- ComfyUI on an RTX 3060 12 GB, image models: https://specpicks.com/reviews/comfyui-rtx-3060-12gb-local-image-generation-2026
- Video on 12 GB, Wan 2.2 TI2V-5B: https://localaimaster.com/blog/local-text-to-video-low-vram
- LTX-2 VRAM on consumer cards: https://localaimaster.com/blog/ltx-2-local-setup-guide
- LTX-2.5 sizes and licence: https://creativeaishow.com/ltx-2-5-the-free-open-weights-ai-video-model-with-native-audio-and-the-real-vram-bill/
- HunyuanVideo-Foley ComfyUI nodes and VRAM: https://github.com/phazei/ComfyUI-HunyuanVideo-Foley ; upstream https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley
- MMAudio weights licence: https://huggingface.co/AEmotionStudio/mmaudio-models/blob/main/README.md ; upstream https://github.com/hkchengrex/MMAudio
- ACE-Step 1.5 licence, VRAM, speed: https://gigazine.net/news/20260204-ace-step-music-generation/ ; ComfyUI support https://www.comfyui.org/en/ace-step-15-is-now-available-in-comfyui
- Kokoro-FastAPI native start and licence: https://github.com/remsky/Kokoro-FastAPI
- LiteLLM auto routing (semantic router deprecated): https://docs.litellm.ai/docs/proxy/auto_routing
- Open WebUI pipe functions: https://docs.openwebui.com/features/plugin/functions/pipe
- Open WebUI with ComfyUI, stock workflow rejected without a workflow and node map: https://github.com/thekaveh/atlas/wiki/Service-Open-Webui
