# Knowledge base

What a newcomer needs to understand about the subjects this stack is built on. These files explain the domain:
what the ideas are, the numbers that matter, what we measured, and where to read more. They do not repeat setup
steps ([manuals](../manuals/)), choices and their reasons ([design/DECISIONS.md](../design/DECISIONS.md)) or the raw
research notes ([research/](../research/README.md)); they link to them.

Files are kept current: when understanding improves, the explanation is rewritten and a dated line is added under
**Changes** at the bottom of the file.

## Reading order

**Start here**

1. [local-llm-inference.md](local-llm-inference.md): how a model runs on one consumer GPU: weights, quantization,
   VRAM versus RAM, the KV cache, prefill and decode speed, mixture-of-experts offload, Ollama settings. For anyone
   who changes `machines/*.yaml` or wonders why the 9B beat the 35B here.
2. [llm-gateway-and-routing.md](llm-gateway-and-routing.md): how clients talk to models through LiteLLM: the
   OpenAI and Anthropic formats, tool calls, aliases, routers, retries, hooks, and Claude Code on a gateway. For
   anyone who touches `infrastructure/litellm/` or `scripts/stacklib/litellm_build.py`.

**Foundations for the private-first plans**

3. [privacy-for-llm-systems.md](privacy-for-llm-systems.md): the privacy boundary, why advice is not enforcement,
   detecting personal data, secrets and sensitive media, consent, measuring a detector, and identity basics. For
   anyone working on the privacy gate (S1-S8) or reviewing a plan.
4. [confidential-computing.md](confidential-computing.md): how a cloud VM can process data its provider cannot read:
   SEV-SNP, TDX, attestation, key brokers, and what the provider still sees. For Plan A.

**Running it on Windows**

5. [windows-service-hosting.md](windows-service-hosting.md): processes, consoles, job objects, Smart App Control,
   pid files, the tray app and Task Scheduler. For anyone debugging a service that will not start or stay up.
6. [agent-file-isolation.md](agent-file-isolation.md): accounts, NTFS permissions and why an agent's own settings
   cannot keep it out of personal files. For the isolation plan.

**Drives**

- [storage-and-drives.md](storage-and-drives.md): sequential and random reads, latency, USB link speeds, why a
  USB-C plug's orientation can matter, and why models can live on a USB drive but tools cannot. For anyone choosing
  folders in the installer or reading the **Check drive speed** step.

**Agents and how the stack improves**

7. [coding-agents-and-self-improvement.md](coding-agents-and-self-improvement.md): agent loops, subagents,
   instruction and memory files, skills, MCP, and the human-gated retro and eval loop. For anyone editing `agents/`,
   skills or the retro.
8. [llm-observability-and-cost.md](llm-observability-and-cost.md): tokens, prices, latency, traces and spans, what
   to log and what not to, and the tray's usage figures. For anyone reading the Usage tab or changing tracing.

**Multimodal: images, video, music, speech and routing**

9. [media-generation-on-local-gpus.md](media-generation-on-local-gpus.md): how diffusion models make images, video
   and music, how they use memory, ComfyUI, model families and licences, hardware tiers and sharing one GPU with the
   chat model. For anyone working on ComfyUI or the GPU mode.
10. [video-with-audio.md](video-with-audio.md): a chain of models versus one joint audio-video model, the hardware
    rule, the software that runs LTX-2, and mixing sound to a loudness target. For the video packages.
11. [speech-and-vision.md](speech-and-vision.md): dictation with Whisper, voices with Kokoro, reading images with the
    chat model, and the privacy points. For the vision and speech packages.
12. [routing-across-models-and-media.md](routing-across-models-and-media.md): decision trees for every routing
    stage, from what kind of request it is to who owns the GPU, and what happens when things change mid-chat. For
    the "Auto" router and the GPU mode.

**Elsewhere in the repo**

- UX: the `/ux-rules` skill carries its own researched catalog of 122 UX rules with evidence grades and sources, in
  [.claude/skills/ux-rules/references/](../../.claude/skills/ux-rules/references/README.md).
- Raw research and critiques from 2026-10-24: [research/README.md](../research/README.md).
- Anthropic API facts used by the gateway: [research/anthropic-facts-2026-10.md](../research/anthropic-facts-2026-10.md).

## Glossary

| Term | Meaning |
|---|---|
| Agent loop | A model that calls tools, reads the results and decides the next step until the task is done. |
| Alias | A model name the gateway exposes (for example `local-primary`) that maps to one or more real deployments. |
| Attestation | A signed report from the CPU that says what software a confidential VM booted, checked before it gets keys. |
| ComfyUI | A local program that runs image, video, audio and music models as workflows of nodes, with an HTTP API. |
| Confidential VM | A virtual machine whose memory is encrypted by the CPU, so the host and cloud provider cannot read it. |
| Context length (`num_ctx`) | How many tokens a model can consider at once: prompt plus answer. Costs memory through the KV cache. |
| Data class | The label on a deployment saying whether data sent there stays private (`private`) or leaves (`external`). |
| Decode | Generating the answer one token at a time; usually limited by memory bandwidth. |
| Department | One of the six agent roles (`app-dev`, `testing`, `security`, `devops`, `code-review`, `docs`), defined in `agents/*.yaml`. |
| Deployment | One concrete model behind the gateway (a provider, a model name and its options). |
| Diffusion model | A model that makes an image, video or sound by removing noise from a random start, one step at a time. |
| Distilled model | A version trained to finish in far fewer steps (4-8 instead of 20-50), with a small loss in quality. |
| Ducking | Lowering music automatically while a voice speaks. |
| Embedding | A list of numbers that represents the meaning of a text, used for search and similarity. |
| Eval gate | A set of tests a prompt or routing change must not get worse on before it is merged. |
| Foley | Sound effects made to match what happens on screen: steps, doors, impacts. |
| GGUF | The file format llama.cpp and Ollama use to store a model's weights and metadata. |
| GPU mode | The planned tray switch that gives the GPU to chat (Ollama) or to media (ComfyUI). |
| Job object | A Windows group of processes; with kill on close, all of them end when the job closes. |
| Joint audio-video model | One model that makes picture and sound together in one pass (LTX-2.x). |
| KV cache | Memory that holds what the model has already read, so it does not reread the whole context for each token. |
| Latent | The compressed form of an image, video or sound that a diffusion model works on. |
| LUFS | Loudness units relative to full scale: the unit for how loud a mix sounds; -16 LUFS is a common web target. |
| MCP | Model Context Protocol: a standard way for an agent to call tools provided by a separate server. |
| mmap | Mapping a file into memory so the operating system loads pages on demand instead of copying the whole file. |
| MoE (mixture of experts) | A model that uses only a few of its many sub-networks (experts) for each token, so active size is far below total size. |
| Mux | Combining a video track and an audio track into one file without re-encoding them. |
| NTFS ACL / ACE | The permission list on a file or folder (ACL) and one entry in it (ACE), which allows or denies an account. |
| Pid | Process id: the number Windows gives a running process. Windows reuses them. |
| Pinning (department) | Keeping the department the router chose for the rest of a chat, unless the owner switches with `@`. |
| Pipe function | An Open WebUI plug-in that appears as a model and can forward each request to another model. |
| Prefill | Reading the prompt before the first answer token; fast because it processes many tokens at once. |
| Privacy boundary | The line inside which data may be processed; only private deployments are inside it. |
| Privacy gate | The planned local service that classifies requests and refuses sensitive data before it can leave. Not built yet. |
| Profile A / profile B | Claude Code on the owner's subscription (A) or pointed at the local gateway (B). |
| Quantization | Storing weights with fewer bits (for example about 4 instead of 16) so a model fits in less memory. |
| Recall / precision | Of all sensitive items, the share the detector caught (recall); of all items it flagged, the share that were sensitive (precision). |
| Router (complexity router) | Gateway logic that picks a tier for each request; here a fast heuristic, no model call. |
| Skill | A folder with a `SKILL.md` that gives an agent instructions and resources for one kind of task. |
| Smart App Control | A Windows feature that blocks unsigned or unknown programs and modules by reputation. |
| Span / trace | One timed step of a request (span) and the record of a whole request (trace). |
| STT / TTS | Speech to text (dictation) and text to speech (reading answers aloud). |
| Tier | A level of model capability in a department's router (for example `local-small`, `local-primary`). |
| Token | A small piece of text a model reads or writes; prices and speeds are counted in tokens. |
| Tool call | A structured request from the model to run a function, whose result is sent back for the next turn. |
| Unified memory | One memory shared by CPU and GPU (DGX Spark, Ryzen AI Max, Apple silicon): large, but slower than a desktop card's VRAM. |
| V2A (video to audio) | A model that watches finished video frames and makes matching sound. |
| VAE | The part of a media model that compresses pixels or sound into a latent and decodes it back. |
| Vision-language model | A model that reads images as well as text; Qwen 3.5 is one. |
| VRAM | The GPU's own memory; fast, but small (12 GB on SEKAIHOME). |

## Changes

- 2026-11-01: first version: eight topic files, reading order and glossary.
- 2026-11-01: four multimodal chapters (9-12) and their glossary terms.
