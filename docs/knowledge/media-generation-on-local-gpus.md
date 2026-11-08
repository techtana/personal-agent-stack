# Making images, video and music on one consumer GPU

## What this is and why the project needs it

The owner wants the stack to make pictures, videos and music, not only text. These jobs use a different kind of
model from the chat model. They are called **diffusion models**. They run in a different program (ComfyUI, not
Ollama). They also want almost all of the graphics card while they work. On the reference machine, an RTX 3060 with 12 GB, that
means the chat model and a media model cannot both stay loaded. This page explains how these models use memory, which
ones fit which hardware, what their licences allow, and how the stack shares one GPU between chat and media. The plan
that builds on it is [../design/plans/2026-11-01-multimodal-stack.md](../design/plans/2026-11-01-multimodal-stack.md).

Read [local-llm-inference.md](local-llm-inference.md) first. It explains VRAM, RAM, quantization and offload, which
this page uses without repeating.

## The ideas, built up from zero

### A diffusion model starts from noise and cleans it up

A chat model writes one token at a time. A diffusion model works differently. It starts with random noise the size of
the picture. Then it removes a little noise in each **step**, guided by your prompt, until a clear picture is left.
Think of a sculptor who takes many small passes over a rough block. Each pass is one run of the whole network.

Two numbers follow from this:

- **Steps.** A normal model takes 20-50 steps. A **distilled** or "turbo" model is trained to finish in far fewer:
  FLUX.1 schnell in about 4, Z-Image-Turbo and the LTX-2 distilled model in about 8. Fewer steps means less waiting,
  usually with a small loss in quality.
- **Size of the work.** A bigger picture, more frames or a longer clip means more numbers to clean in each step. Time
  and memory both grow with it.

The sculptor analogy stops here: a sculptor sees the whole statue, but the model works in a compressed space, which is
the next idea.

### Three parts: text encoder, denoiser, VAE

Most media models have three separate networks:

| Part | Job | Size note |
|---|---|---|
| Text encoder | Turns the prompt into numbers the denoiser understands | Can be large. LTX-2 uses Gemma 3 12B as its text encoder. Wan uses a T5-family encoder. |
| Denoiser (often a "diffusion transformer") | Removes noise, step by step | The biggest part. "6B", "14B" and "22B" model names count this part. |
| VAE (variational autoencoder) | Compresses pixels into a small **latent** space before the steps, and decodes the result back into pixels after them | Small, but decoding a long video at the end can need a burst of memory. |

The denoiser works on the latent, not on pixels. A latent is many times smaller than the picture, which is why a
1024-pixel image is affordable at all. Audio models work the same way with an **audio VAE**.

Why this matters here: the three parts do not all need to sit in VRAM at once. ComfyUI can load the text encoder, use
it, move it out, then load the denoiser. That is how a model whose files add up to more than 12 GB can still run on a
12 GB card, slowly.

### Why media models fill the card

A chat model's decode speed depends mostly on how fast it can read its weights (memory bandwidth). A diffusion model
does far more arithmetic per step, on every position of the latent at once. Both compute and bandwidth matter, and the
model must keep its weights plus the working latent in fast memory. In practice a media model wants nearly all of the
VRAM for the length of one job.

Typical numbers on an RTX 3060 12 GB (web reports, not measured here):

| Model and setting | VRAM | Time |
|---|---|---|
| SD 1.5, 512 px, 20 steps | ~3 GB | under 2 s per image |
| SDXL, 1024 px, 30 steps | ~9-11 GB | 6-12 s per image |
| FLUX.1 schnell int8, 1024 px, 4 steps | ~10 GB | 3-5 s per image |
| FLUX.1 dev int8, 1024 px, 28 steps | ~10 GB | 15-22 s per image |
| Wan 2.2 TI2V-5B fp8, 720p, 5 s clip | all 12 GB with offload; 24-32 GB system RAM | 5-12 min per clip |

### Number formats: bf16, fp8, int8, nvfp4, GGUF

Media weights come in several precisions, like chat models:

- **bf16 / fp16**: full quality, largest. The LTX-2.5 denoiser alone is about 42 GB in bf16.
- **fp8**: about half the size. Native fp8 arithmetic needs an RTX 40-series (Ada) or newer card.
- **int8**: also about half. RTX 30-series cards (Ampere, like the 3060) have int8 tensor cores, so int8 builds run
  there at full speed. LTX-2.5's official ComfyUI template uses an int8 build.
- **nvfp4**: about a quarter of the size; needs an RTX 50-series (Blackwell) card.
- **GGUF**: the same file format as the chat models, used by community ComfyUI loaders to run media models at about
  3-5 bits. Lower bits fit smaller cards but show more visible quality loss.

On the reference machine, prefer int8 and GGUF builds. An fp8 file still loads on a 3060, but it is converted on the fly and
gains nothing in speed.

### Offloading: running a model bigger than the card

When the weights do not fit, the program keeps part of them in system RAM and moves blocks to the GPU when needed
("block swap", "weight streaming", ComfyUI `--lowvram`). It works, but every step now waits for data to cross the PCIe
bus, so a job can take several times longer. Offloading also needs a lot of free system RAM: guides ask for at least
24 GB and recommend 32 GB for video. On the reference machine the usual desktop leaves about 11-12 GB free, so video jobs need the
desktop apps closed.

### ComfyUI: one program for every media model

**ComfyUI** is a local program where a job is a **workflow**: a graph of nodes (load model, encode prompt, sample,
decode, save). It runs image, video, audio and music models in the same way and unloads models between nodes when
memory runs short. Three things make it the right fit for this stack:

- Model makers ship ComfyUI support first. Lightricks recommends it for LTX-2; ACE-Step 1.5 has a built-in template;
  Wan 2.2 and Z-Image-Turbo run natively.
- It has an HTTP API: post a workflow to `/prompt`, read results from `/history`, free memory with `/free`, check
  health with `/system_stats`. Open WebUI uses this API for its image button.
- Workflows are JSON files, so the repo can keep them under version control.

Two cautions. **Custom nodes** are Python code from third parties and run with full access, so install only the ones
a saved workflow needs and pin their versions. And ComfyUI is a PyTorch program with many compiled modules, which
Smart App Control may block one by one ([windows-service-hosting.md](windows-service-hosting.md)).

Ollama added experimental image generation in January 2026, but only on macOS and on Linux with CUDA. It does not help
on this Windows machine.

### Model families the plan uses

| Job | Model | Licence | Notes |
|---|---|---|---|
| Text to image | Z-Image-Turbo (6B) | Apache-2.0 | Photorealistic; English and Chinese text in images |
| Text to image | FLUX.1 schnell | Apache-2.0 | 4 steps |
| Text to image | FLUX.2 klein 4B / 9B | 4B Apache-2.0; 9B non-commercial | Klein reported to run in about 13 GB of VRAM |
| Style transfer, image prompts | SDXL + IP-Adapter | SDXL: CreativeML OpenRAIL++-M; IP-Adapter: Apache-2.0 | Uses a reference picture as the style |
| Text or image to video | Wan 2.2 TI2V-5B | Apache-2.0 | 720p, 24 fps, about 5 s |
| Video with sound in one pass | LTX-2 / LTX-2.5 | LTX-2 community licence: free under $10M yearly revenue; gated download | See [video-with-audio.md](video-with-audio.md) |
| Sound effects for a video | HunyuanVideo-Foley; MMAudio | Tencent's own licence; MMAudio weights CC BY-NC 4.0 | Both restricted; personal use needs an owner decision |
| Music | ACE-Step 1.5 | MIT | Under 4 GB VRAM reported |

Licence words mean different things. **Apache-2.0** and **MIT** allow commercial use. **CC BY-NC** forbids
commercial use. "Community" licences are custom: read each one, because some limit revenue, users or countries.

### Hardware tiers

How much media work a machine can do depends mostly on VRAM, then on system RAM, then on memory bandwidth.

| Tier | Example | What fits well |
|---|---|---|
| 12 GB | RTX 3060 (the reference machine), RTX 5070 | Images at 1024 px; short 720p clips with Wan 2.2 5B and offload; music; video sound as separate steps |
| 16 GB | RTX 5070 Ti, 5080 | Same, faster; still too small for the LTX-2.5 int8 denoiser (about 21.5 GB) |
| 24 GB | RTX 3090, 4090 | LTX-2.5 int8 fully loaded for about 5 s clips (22.7 GiB measured by a community recipe); a 3090 takes about 2.5 min per distilled 5 s clip |
| 32 GB | RTX 5090 | LTX-2.5 at about 25 s for a 4 s 720p clip (NVIDIA guide); 8 s clips stream weights and take about 3 min |
| 128 GB unified memory | DGX Spark, Ryzen AI Max, Apple silicon | Everything fits, but slowly. One report: Wan 2.2 5B took about 14 min for a 5 s clip on a Spark, against about 3 min on a 12 GB RTX 5070 |

Unified-memory machines share one large memory between CPU and GPU. They are excellent for big chat models that do
not fit a gaming card. For diffusion they are limited by lower memory bandwidth (about 273 GB/s on the Spark, against
about 672 GB/s on an RTX 5070) and less GPU compute, so a desktop card with less memory is often faster.

### Sharing one GPU between chat and media

On the reference machine the 9B chat model holds 6.2 GB of weights (8.0 GB on the card in total at 16k) and stays loaded on
purpose (`keep_alive: -1`), and the autocomplete model holds another 1.3 GB. A media model wants the rest and more.
There are three ways to share:

1. **Take turns, explicitly.** Unload the chat models (`POST /api/generate` with `"keep_alive": 0` for each model
   that `/api/ps` lists), run the media job, then free ComfyUI's memory (`POST /free`). The next chat reloads the 9B.
   A cold load from the USB SSD took 130-161 s here; a reload from the operating system's file cache should be
   faster, but it is not measured yet.
2. **Let ComfyUI offload.** Start it with `--lowvram --reserve-vram 1.0`. A job then runs beside the loaded chat
   model, slower.
3. **Automatic hand-over** per request. This needs our own code in the path of every image request, because Open
   WebUI calls the image engine outside its chat filters.

The plan uses 1 as a tray switch ("GPU mode") with 2 as a safety net. A 32 GB card does not remove the problem: the
9B (about 8 GB) plus LTX-2.5 int8 (about 22.7 GB) leaves almost nothing free.

## Rules of thumb and typical numbers

- One large GPU model at a time on 12-24 GB. Plan the hand-over, do not hope for it.
- Images: about 10 GB and seconds per picture on a 3060. Video: all the VRAM, lots of RAM, and minutes per clip.
- Distilled models (4-8 steps) are the right default on consumer cards.
- Prefer int8 or GGUF builds on an RTX 30-series card; fp8 gains nothing there.
- For video, close desktop apps first: offload needs 24-32 GB of system RAM.
- A unified-memory box is for big chat models, not for fast video.
- Check every licence before naming a model in code or docs.

## Common misconceptions and edge cases

- **"If the files add up to more than my VRAM, it cannot run."** It can, with offload, but much more slowly. The
  question is whether it is fast enough to use.
- **"More memory always means faster."** Not for diffusion. A 128 GB unified-memory box fits more, but a 12 GB
  desktop card can finish a video clip several times sooner.
- **"Open weights means free to use for anything."** No. MMAudio's weights are non-commercial; LTX-2 has a revenue
  limit; FLUX.2 klein 9B is non-commercial.
- **"The VAE is small, so it never runs out of memory."** Decoding a long clip at the end is a common failure point:
  10 s LTX-2.5 clips can stall at the decode on 24 GB. Tiled VAE decoding reduces the peak.
- **"Ollama can do images now."** Only on macOS and Linux with CUDA, and only a few models.

## How the project uses it

- ComfyUI becomes a native service (`comfyui`, port 8188), off by default, managed like the others by `stack.py` and
  the tray (plan package M4).
- Open WebUI's image button calls ComfyUI with a saved workflow and node map. The stock workflow fails without them
  ([atlas wiki note](https://github.com/thekaveh/atlas/wiki/Service-Open-Webui)).
- Saved workflows live in `config/comfyui/workflows/`; licences and versions in `config/comfyui/MODELS.md`.
- Open licences only (decision D-M3, 2026-11-01): Apache-2.0, MIT and similar, plus SDXL's OpenRAIL++-M. The
  restricted rows in the model-family table (LTX-2, HunyuanVideo-Foley, MMAudio, FLUX.2 klein 9B) are not used.
- Style transfer uses Open WebUI 0.12.3's native image edit with its own ComfyUI workflow (`ENABLE_IMAGE_EDIT`,
  `IMAGES_EDIT_COMFYUI_WORKFLOW`).
- The tray gains a GPU mode switch; ComfyUI starts with `--lowvram --reserve-vram 1.0`.
- Model files, caches and outputs: only on the drives and folders the owner selects (`agent_access.allowed_roots`).
  Every tool's cache path is set explicitly, so nothing lands in a default folder outside the selection.

## What we found

Nothing is measured on the reference machine yet. Every timing above is from web reports read on 2026-11-01. Spike M-S0 in the plan
replaces them with local numbers, which will be added here.

## Open questions

- Does ComfyUI run under Smart App Control, and which install route works (desktop installer, portable, uv venv)?
- How long does the 9B take to reload from the file cache after a media job?
- Does Wan 2.2 5B finish a 5 s 720p clip in under 20 minutes with 32 GB of RAM and desktop apps closed?
- Which edit model fits 12 GB well enough for style transfer?

## Sources and further reading

| Source | Author / year | Good for |
|---|---|---|
| [ComfyUI on an RTX 3060 12 GB](https://specpicks.com/reviews/comfyui-rtx-3060-12gb-local-image-generation-2026) | SpecPicks, 2026 | image model VRAM and speed on this card |
| [Local text-to-video on low VRAM](https://localaimaster.com/blog/local-text-to-video-low-vram) | LocalAIMaster, 2026 | Wan 2.2 5B on 12 GB, RAM needs, flags |
| [LTX-2.5 hardware guide](https://runaihome.com/blog/ltx-2-5-local-ai-video-hardware-guide-2026/) | RunAIHome, 2026-08 | VRAM and speed by card, int8 versus fp8 |
| [LTX-2.5 sizes and licence](https://creativeaishow.com/ltx-2-5-the-free-open-weights-ai-video-model-with-native-audio-and-the-real-vram-bill/) | Creative AI Show, 2026 | file sizes, GGUF levels, licence terms |
| [DGX Spark vs PC for image to video](https://forums.developer.nvidia.com/t/image-to-video-generation-using-the-spark-vs-pc/370077) | NVIDIA forums, 2026 | unified memory versus a desktop card |
| [Ollama image generation](https://gigazine.net/gsc_news/en/20260123-ollama-ai-image-generation/) | GIGAZINE, 2026-01 | what Ollama's image support covers |
| [ACE-Step 1.5](https://gigazine.net/news/20260204-ace-step-music-generation/) | GIGAZINE, 2026-02 | music model licence and VRAM |
| [MMAudio weights](https://huggingface.co/AEmotionStudio/mmaudio-models/blob/main/README.md) | Hugging Face, 2026 | licence and file sizes |
| [ComfyUI-HunyuanVideo-Foley](https://github.com/phazei/ComfyUI-HunyuanVideo-Foley) | phazei, 2026 | Foley VRAM, fp8, block swap |
| [Open WebUI and ComfyUI note](https://github.com/thekaveh/atlas/wiki/Service-Open-Webui) | atlas wiki, 2026 | why a workflow and node map are required |

## Changes

- 2026-11-01: first version, from the multimodal research of that day.
