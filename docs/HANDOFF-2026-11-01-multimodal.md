# HANDOFF - 2026-11-01 - multimodal stack, for the next Claude Code session

**Status:** open. Written in a cloud session that could read this repository and the web but not SEKAIHOME. Nothing in
the plan has been run on the machine.

You are continuing the design and build of the multimodal features of this stack: vision, speech, image generation
and style transfer, **video with audio**, music, web search, and a router that picks an expert per message. The plan
is [design/plans/2026-11-01-multimodal-stack.md](design/plans/2026-11-01-multimodal-stack.md). Read this file first,
then the plan, then work through section 4 below.

## 1. Owner's goals (authoritative)

1. One private stack on SEKAIHOME for writing, coding, software architecture, science, art critique, image
   recognition, web search, image generation, style transfer, video generation, music and speech.
2. **Generated videos must have audio**: sound effects in time with the picture, with optional narration and music.
3. The right "expert" answers each message without the owner picking a model by hand.
4. The existing principles still hold: private first, native services (no Docker or WSL2), composed from open-source
   tools, human-gated pull requests, one source of truth with generated files.

## 2. Ground rules for this work

- Follow `AGENTS.md`. In particular: never edit generated files (rule 1); private first (rule 9); one bounded task
  per pull request, with a checkpoint (rule 5).
- **Never read, write, list or stage anything on the D: drive or in the owner's OneDrive folders**, even though
  model files live on D: today. When a step needs a file there (a model download, a model path), stop, tell the owner
  exactly what to copy where, and let him do it. Paths go into `machines/SEKAIHOME.yaml` only as values he gives you.
- The repository is public. Do not commit personal data, file names from personal folders, or secrets.
- Do not start or stop the stack's services from your tool shell to keep them running; the tray owns them
  (`memory/lessons.md`, 2026-10-25). Short test runs are fine; say what you started and stop it again.
- Any install that changes the machine (ComfyUI, Kokoro, models, winget packages) waits for the owner's go-ahead in
  the same session. Spike results go into `memory/state.md` as measurements with dates.
- Check every model's licence before naming it in code or docs (lesson 2026-10-26). Record it in
  `config/comfyui/MODELS.md` when that file exists.
- Use few research subagents, staggered (lesson 2026-11-01). Fetch primary pages directly when search runs out.

## 3. What is known and what is not

Known from this repository (verified there by earlier sessions, see `memory/state.md`):

- The 9B primary holds 6.2 GB of weights at 32k (8.0 GB on the card in total at 16k) and stays loaded; a cold load from the USB SSD took
  130-161 s.
- Smart App Control blocks unsigned compiled Python modules file by file; it broke Phoenix.
- About 11-12 GB of the 32 GB RAM is free under the usual desktop load; C: has about 36 GB free.
- Open WebUI 0.12.3, LiteLLM 1.106.3 and Ollama 0.40.11 are installed.

Read on the web on 2026-11-01 and **not measured here** (plan sections 5 and 6 list the sources):

- `qwen3.5:9b` accepts images.
- Wan 2.2 TI2V-5B makes a short 720p clip in about 5-12 minutes on 3060-class cards.
- HunyuanVideo-Foley runs under 8 GB in fp8; MMAudio weights are non-commercial; ACE-Step 1.5 is MIT and needs
  under 4 GB; Kokoro-FastAPI starts natively on Windows from a uv script.
- LTX-2.x makes picture and sound in one model but does not fit 12 GB without heavy offload.

Possibly stale: `memory/state.md` says the 2026-11-01 tray UX branch is not merged, but `main` contains PR #15 from
that branch. Check and correct the state file.

## 4. What to do, in order

### Session 1: deep planning (no machine changes)

1. Run `uv run scripts/stack.py doctor` and `status`. Note anything that contradicts section 3.
2. Read the plan end to end. Check its claims against the code paths it names (`litellm_build.py`, `agents_build.py`,
   `services.py`, `settings.py`, `smoke.py`), and against the installed Open WebUI 0.12.3 for the audio, image and
   web-search setting names. Fix the plan where it is wrong.
3. Settle decisions D-M1 to D-M8 (plan section 12) with the owner, a few questions at a time. Record each in
   `docs/design/DECISIONS.md` (replace the "Pending" note) and in the plan.
4. Turn packages M1-M7 into issue-sized tasks with acceptance checks. Put the task list in the plan under a new
   "Tasks" section, or open GitHub issues if the owner prefers.
5. Open a pull request with the planning changes. Stop for review.

### Session 2: spike M-S0 (owner present; changes the machine)

Run S0a-S0f from the plan. Ask before each install. Record every time, VRAM and RAM figure in `memory/state.md`, and
every surprise in `memory/lessons.md`. Update the plan's model choices from the results. One pull request.

### Sessions 3 onward: build, one package per pull request

Order: M1 (vision, departments) -> M2 (speech) -> M3 (Auto router) -> M4 (ComfyUI, images, GPU mode) -> M5a (video
with audio, music, `media mux`) -> M5b (`make_video` tool) -> M6 (web search, only if the owner turned it on) -> M7
(docs closure). For each package:

- write or extend tests first where the code is testable without a GPU (build output, service commands, the ffmpeg
  filter graph);
- run `uv run scripts/stack.py build` and `uv run --with pytest pytest -q`;
- run the package's acceptance check on SEKAIHOME and paste the result into the pull request;
- update README (configuration, commands, known issues, path forward), the manuals, `DECISIONS.md` and
  `memory/state.md`.

## 5. Definition of done for the whole plan

- In Open WebUI, the "Auto" model routes a writing, a science, an architecture, a code and an image question to the
  right department, and says which one it chose.
- An attached photo gets a correct description; the microphone dictates; the speaker reads answers aloud.
- The image button makes an image; a style-transfer workflow restyles an uploaded photo.
- One prompt makes a 5 s 720p MP4 with synchronised sound effects, and optional narration and music, mixed to the
  plan's loudness targets.
- A music prompt makes a track.
- Nothing calls a cloud API, except web search if the owner turned it on and recorded that decision.
- `smoke --media` passes; tests pass; the manuals describe each feature.

## 6. Kickoff prompt

Paste this into Claude Code opened on this repository on SEKAIHOME:

```
Read docs/HANDOFF-2026-11-01-multimodal.md and follow it. Start with Session 1 (deep planning, no machine
changes): check the plan in docs/design/plans/2026-11-01-multimodal-stack.md against the code and the installed
versions, then walk me through decisions D-M1 to D-M8 a few at a time, then break M1-M7 into tasks with acceptance
checks. Never touch the D: drive or my OneDrive folders; tell me what to copy instead. Open a pull request at the
end and stop.
```
