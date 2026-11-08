# Design decisions

Running log, newest first. Never delete an entry; mark a reversed one "Superseded by <date>". Each line gives the
date, the decision, why, the alternatives turned down, and where it came from. Decisions recorded in more detail
elsewhere link there. Architecture decision records (ADR format) live in [../decisions/](../decisions/README.md).

"Pending" marks a decision made in an open pull request that is not on `main` yet. When the pull request merges, the
entry stays and gets a "Done <date>" note.

## 2026-11-07

- **Pending: the installer asks which features to install, shows what each takes on this PC, and the tray shows what
  is installed.** Asked by the owner: choose the features, with the required ones fixed; see each one's CPU and GPU
  load while choosing; see in the tray what is installed and linked to the stack; run the installer again for more.
  - One catalog, `stacklib/features.py`, for the installer's first page, the tray's Features card and
    `stack.py features`. Required: the local models and the gateway (with the orchestrator and the tray). Optional:
    Open WebUI, Phoenix, images, voice typing, recordings in Claude Desktop, OpenClaw.
  - The installer adds features and never turns one off. Installed features that are on are ticked and locked;
    Settings in the tray turns them off. A second run cannot remove anything by accident.
  - Status is read from the system every time (tool environments, files under the media folder, the profile's
    switches, Claude Desktop's and OpenClaw's configs), never from a stored list of what the installer chose, which
    would drift after changes by hand.
  - Estimates: the reference PC's measurements (memory/state.md) and the install sizes measured on 2026-11-07, the
    chat model's GPU memory from Ollama when it is loaded, the rest marked as estimates. A fit check adds up the choice
    against this PC's GPU, RAM and processors.
  - First ticks: Open WebUI and OpenClaw on, images on a card with 10 GB or more, Phoenix off under Smart App Control,
    voice typing and recordings off (a global hotkey; a change to Claude Desktop's config).
  - Rejected: uninstalling from the installer (deleting a feature's files is a separate decision); a stored record of
    installed features; benchmarking each feature during setup (minutes of downloads and GPU work before anything is
    chosen).

- **Pending: machine profiles are local, and the repository names no person or computer.** Asked by the owner after
  finding the computer name in the repository: values like that are set during install and never committed, on any
  branch. `machines/<HOST>.yaml` is ignored by git and written by the installer; a linked worktree reads the main
  checkout's profile; docs say "the reference machine", "the owner" and `<owner>`; the generated LiteLLM header drops
  the machine name; `tests/test_personal_info.py` scans files git would publish for this machine's names and git email
  (read at test time, plus a gitignored `.personal-terms`). Rejected: renaming the tracked profile to a neutral name
  (the next machine's `doctor --write-profile` would publish its name again), a per-user config folder outside the
  repository (bigger change; every doc names `machines/<HOST>.yaml`), and a denylist of names inside the repository
  (it would publish them). Not covered: git history and GitHub's pull request pages.
- **Pending: a weekly security and confidentiality audit of the Claude setup (`/claude-security-audit`).** Asked by
  the owner: regularly look for vulnerabilities and for new Claude settings that improve confidentiality and safety,
  and always replace the owner's identity with placeholders where it is written down. The skill reports on settings
  and never changes them: the owner's settings deny Claude edits, and AGENTS.md rule 9 warns against add-ons that
  imply enforcement. It gains an explicit exception for an audit that says plainly what it cannot enforce. The skill
  does replace identity, through a deterministic `scrub` that never puts the values in tool calls. A desktop
  scheduled task runs it weekly from a throwaway worktree and opens a pull request for repository fixes, as
  `skills-sync` does. A standing rule in the owner's `~/.claude/CLAUDE.md`, and AGENTS.md rule 10, cover every other
  session.
  - Sources: OSV for advisories, and the npm registry, the docs (`settings-reference.md`, `env-vars.md`) and the
    changelog for what's new; only package names and versions leave the machine.
  - Rejected:
    - editing settings automatically;
    - a cloud routine, which can't see local configuration;
    - treating the computer name as identity to replace, since machine profiles are named after it (it is reported). Superseded by
      2026-11-07 (the entry above): machine profiles are local, and the repository names no computer.

- **Pending: voice typing in every app, as the stack service `dictation`.** Asked by the owner: Whisper on this machine
  instead of typing into text fields, documents and Logseq, with a button, a hotkey, a stop after quiet, and text as
  you speak or cleaned up after you finish. A Windows desktop app (floating mic button, Ctrl+Alt+D) rather than a
  browser extension, which cannot reach Logseq desktop or Word. faster-whisper large-v3-turbo on the GPU in its own
  environment under `media.root`, using Ollama's CUDA 12 cuBLAS; Silero VAD per 32 ms frame; WinMM for the microphone;
  the cleanup through the private alias `local-small` with JSON output and thinking off. Rejected: whisper.cpp's
  unsigned binaries and PortAudio-based audio packages (Smart App Control), Open WebUI's CPU Whisper as the engine, an
  always-open microphone, Ctrl+Alt+Space (the Claude desktop app's quick entry). D-M4 is unchanged. Plan and
  measurements: [plans/2026-11-07-voice-typing.md](plans/2026-11-07-voice-typing.md).

## 2026-11-01

- **Pending: the installer checks drive speed, sets up the Hugging Face cache and installs OpenClaw.** Asked by the
  owner after `winsat` showed the models drive at 41 MB/s (USB 2.0 link) and 376 MB/s with the plug turned over.
  The speed check uses `winsat` only as administrator (without it, `winsat` prints nothing) and otherwise times an
  uncached 256 MB test file; it warns and suggests a drive but never moves files. `HF_HOME` goes to
  `<models drive>:\huggingface` (the owner chose `D:\huggingface` over `D:\hf`); the token stays on the internal
  drive. OpenClaw installs with npm on the system drive and upgrades Node.js through winget when it is too old;
  onboarding stays a manual step. Rejected: running `winsat` through a UAC prompt from the background worker.
  Manual: [../manuals/choosing-drives.md](../manuals/choosing-drives.md).
- **Pending: multimodal decisions D-M1 to D-M8, settled with the owner in Session 1.** Source: the plan, section 12;
  [plans/2026-11-01-multimodal-stack.md](plans/2026-11-01-multimodal-stack.md).
  - D-M3: **open licences only** (Apache-2.0, MIT and similar; SDXL's CreativeML OpenRAIL++-M allowed). Out: MMAudio,
    HunyuanVideo-Foley, LTX-2.x, FLUX.2 klein 9B. Rejected: personal use of non-commercial or custom-licence weights,
    labelled.
  - D-M1: video audio comes from the chain (Route A) on every machine. The one-time LTX-2 trial is dropped (D-M3), and
    the `media.video_route` setting waits for an open-licence joint model.
  - D-M2: the Foley model is picked by ear in spike S0e, among open-licence candidates only; with none, back to the
    owner.
  - D-M4: Open WebUI talks to Kokoro and Whisper directly; speech through LiteLLM stays optional.
  - D-M5: **web search with DuckDuckGo, no key, as a per-chat toggle, off by default.** This is an exception to private
    first: the search query leaves the machine; the chat and its model call do not. Rejected: off (the proposed
    default); a keyed API (Brave, Tavily).
  - D-M6: agent sessions work only in the drives and folders the owner selects; the machine profile carries them as
    `agent_access.allowed_roots` (empty means ask), and the build refuses media paths outside them (T08).
  - D-M7: GPU sharing by a tray Chat/Media switch, with ComfyUI always on `--lowvram --reserve-vram 1.0`.
  - D-M8: four new departments (`writer`, `scientist`, `architect`, `art-critic`). An attached image goes to the
    classifier, limited to the vision departments, with `art-critic` as fallback. Rejected: every image to
    `art-critic`.
- **Pending: multimodal features follow one plan,** [plans/2026-11-01-multimodal-stack.md](plans/2026-11-01-multimodal-stack.md):
  vision on the existing `qwen3.5:9b`, speech (Whisper in Open WebUI, Kokoro on the CPU), ComfyUI for images, style
  transfer, video and music, and an "Auto" pipe function in Open WebUI that picks a department per chat. Why: the
  owner wants one private stack for writing, coding, science, art critique, images, video, music and speech. Open:
  D-M1 to D-M8 in the plan (settled above). Source: [handoff](../HANDOFF-2026-11-01-multimodal.md). Done 2026-11-01
  (PR #16).
- **Pending: generated videos carry audio.** Default route: a composed ComfyUI pipeline (Wan 2.2 TI2V-5B, then a
  video-to-audio Foley model, optional Kokoro narration and ACE-Step music, mixed and muxed with ffmpeg). Why: the
  owner requires audio on videos; one-model audio-video (LTX-2.x) does not fit 12 GB without heavy offload. Rejected
  for now: LTX-2.x as the default (to be tried once in spike S0f). Source: the plan, section 6. Done 2026-11-01
  (PR #16); the S0f trial superseded by D-M3 above.
- **Pending: the video route follows the GPU.** Chain under 24 GB of VRAM; joint model (LTX-2.5) for clips of about
  5 s with speech at 24 GB; joint by default from 32 GB, with music mixed in by ffmpeg; chain on unified-memory
  machines. Carried as `media.video_route: chain | joint | auto`. Why: LTX-2.5 int8 needs 22.7 GiB for a 5 s clip,
  and unified memory is bandwidth-limited for diffusion. Source: the plan, section 6;
  [video-with-audio.md](../knowledge/video-with-audio.md). Superseded by 2026-11-01 D-M3 (open licences only): the
  joint model has a custom licence, so every machine uses the chain.
- **Pending: experts are departments on one shared model, not separate models.** Why: a cold load of the 9B took
  130-161 s here, so a model per subject would mean minutes of waiting at each switch. Rejected: LiteLLM's semantic
  router (deprecated); a model per subject. Source: the plan, section 8. Done 2026-11-01 (PR #16).

- **UX reviews use a researched rule catalog packaged as a skill (`/ux-rules`).** 122 rules in 14 categories plus 15
  contested or debunked ones; each rule carries an evidence grade, limits, how to detect it, how to build it and how
  to measure it. The skill refuses to A/B-test deceptive patterns. Why: the owner asked for proven UX rules, organised
  by category, and a way to check a UI against them. Source: PR #13,
  [.claude/skills/ux-rules/references/](../../.claude/skills/ux-rules/references/README.md).
- **Pending: `ux-rules` belongs in the `skills/` library** (convention of 2026-10-31). The commit that moves it
  (`a8400c9`) is on the PR branch but landed after PR #13 merged, so on `main` the skill is still in `.claude/skills/`.
  Source: PR #13 reviewer notes.
- **Run fewer research subagents, or stagger them.** Why: ten parallel agents shared one WebSearch budget, ran it out
  and hit the plan's session limit. Source: `memory/lessons.md`, `7773047`.

## 2026-10-31

- **The owner's own skills are versioned in `skills/`, copied by `stack.py skills-sync`.** One way: a skill deleted
  at its source is reported `orphaned` and removed only in a reviewed commit. Files compare by sha256 with line
  endings ignored. Why: keep skills versioned and reusable by the stack's other clients. Source:
  PR #11, [skills/README.md](../../skills/README.md).
- **Never sync Anthropic's skills, `license: Proprietary` skills, or names under `exclude`.** `job-search-agent` is
  excluded because it holds personal data and the repository is public. Source: PR #11, `skills/sync.yaml`.
- **A weekly Claude desktop scheduled task runs the sync in a throwaway worktree, scans for personal data, runs the
  tests and opens a pull request; it never merges.** Why: human-gated changes, same as the retro loop. Source: PR #11,
  [skills/sync-task-prompt.md](../../skills/sync-task-prompt.md).

## 2026-10-29

- **Proposed: the hard block on AI agents reading personal files is a separate standard Windows account** (`ai-agent`,
  group `AI-Agents`) with NTFS deny entries on personal folders, not any agent's own settings. Why: deny rules,
  hooks and app sandboxes are advisory or off by default on native Windows (`python -c` reads a denied file).
  Rejected: app deny rules as the boundary; WSL2 with the Claude Code sandbox (RAM); a Hyper-V VM per agent (2-4 GB
  RAM, no GPU) except for untrusted one-off runs. Open: D1-D4. The 2026-10-30 checks found D: is exFAT with no
  permissions, so personal data there must move or the drive be reformatted first. Source:
  PR #12, [AGENT-FILE-ISOLATION.md](../plans/AGENT-FILE-ISOLATION.md).

## 2026-10-28

- **PR #8 merged:** the private-only gateway build, the per-process view and the hidden-console service start below
  are on `main` since 2026-10-28. The build also checks Claude Code profile B aliases, and profile B sets
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` and denies WebFetch and WebSearch. Source: PR #8.
- **`stack.py down` leaves Task Scheduler-supervised services to `stack.py tasks stop`.** Source: PR #8 (merge
  conflict resolution); the reason is not recorded there (the 2026-10-26 entry says `tasks stop` disables the task so
  the watchdog does not revive it).

## 2026-10-27

- **Tray window has Overview, Usage and Settings tabs.** Settings writes only the changed keys of
  `machines/<HOST>.yaml` (comments kept), rebuilds, and restarts only what the change affects. Why: the owner wanted
  to change settings and see usage per model without editing YAML or reading traces. Source: PR #9,
  [plan](plans/2026-10-26-tray-status-window.md).
- **Cloud tiers are read-only in the tray.** Turning them on stays a `.env` decision. Why: private first. Rejected:
  a cloud toggle in Settings. Source: PR #9.
- **Apply restarts only a LiteLLM the stack started itself, and asks before restarting Ollama.** If LiteLLM runs
  under a scheduled task or was started elsewhere, the tray says so instead. Rejected: restarting any process on the
  port. Source: PR #9.

## 2026-10-26

- **Private first.** Every request runs on private models (owned hardware or confidential VMs). External model APIs
  are off at install and become an explicit, consented, gated user choice. Why: the provider must not be able to
  read the data. Rejected: automatic Claude escalation by token count or keyword; `cloud.enabled: auto`. Source:
  `be3d566`, [SHARED-COMPONENTS.md section 0](../plans/SHARED-COMPONENTS.md). Supersedes the cloud-tier entries of 2026-10-24.
- **Pending (PR #8; done 2026-10-28): the gateway build is private only.** Routers, fallbacks and defaults name private deployments
  only; the build fails on an external target and refuses `external.enabled: true` until the privacy gate exists.
  Why: enforce private first in generated config, not only in docs. Rejected: `cloud.enabled: auto` (PR #2).
  Source: PR #8, SHARED-COMPONENTS S6.
- **No privacy add-ons for clients outside the boundary** (Claude Code on a subscription, Claude Desktop). A client
  counts as protected only when its sole model endpoint is the gated gateway. Why: such add-ons can only advise but
  suggest enforcement. Source: AGENTS.md rule 9, `memory/lessons.md`.
- **Archive the Google Cloud draft** (Vertex AI, Secret Manager, managed Cloud Run defaults) and replace it with Plan A
  on confidential VMs. Why: its defaults contradicted private first. Source:
  [archive/GCP-DESIGN-DRAFT-2026-10-26.md](../archive/GCP-DESIGN-DRAFT-2026-10-26.md).
- **Build the privacy plans on existing open-source tools** (Presidio, detect-secrets, deface, ExifTool/mat2, LiteLLM
  access groups and request log, winget configure, Authentik/Keycloak, Trustee) and write only glue. Rejected: custom
  detectors, a custom invite service. Source: `6ea3a6c`.
- **The plans remove the orchestrator MCP server, `record_lesson`, Phoenix, prompt-text JSONL traces and automatic
  cloud tiers**; the LiteLLM request log and admin UI replace them. Why: no stored prompt text; departments become
  gateway aliases and Open WebUI models. Still in the tree today. Source: SHARED-COMPONENTS section 5.
- **Identity: Authentik on Plan A, Keycloak on Plan B.** Why: both give TOTP, passkeys, OIDC and invitations; Keycloak
  measured at about 0.5 GB on the reference machine. Rejected: Authentik on Windows; a custom invite service. Source:
  SHARED-COMPONENTS S7, [PLAN-B](../plans/PLAN-B-LOCAL-LED.md) B-S0.
- **The privacy gate uses small spaCy models and embedding exemplars for topics.** Why: `en_core_web_lg` alone is
  978 MB (target 900 MB); zero-shot topic models take 0.5-3 s per text (target 50 ms). Source: SHARED-COMPONENTS V4, G7.
- **NudeNet dropped** for deface/CenterFace (MIT), an RT-DETR person detector (Apache-2.0), Tesseract and Presidio.
  Why: NudeNet's weights are AGPL-3.0. Source: SHARED-COMPONENTS V5.
- **Windows metadata stripping uses ExifTool plus qpdf**; mat2 only where it runs. Why: mat2 does not run natively on
  Windows, and WSL reserves RAM the MoE needs. Source: SHARED-COMPONENTS V11.
- **LiteLLM per-user checks use `custom_auth` with `enable_post_custom_auth_checks: true`.** Why: `user_header_name`
  fails open without Postgres. Source: SHARED-COMPONENTS V2, `memory/lessons.md`.
- **Privacy refusals raise a non-retryable 4xx.** Why: a plain exception becomes HTTP 500, which the router retries
  and may answer from a fallback. Source: SHARED-COMPONENTS V1.
- **Consent is keyed on the Open WebUI chat id**, with a 30-minute per-user fallback. Why: Open WebUI sends the chat id
  only when its header flag is on. Source: SHARED-COMPONENTS V3.
- **Plan defaults:** external models off (G3); a sensitive verdict can never be overridden (G6); generalise/redact
  off (G4). Source: SHARED-COMPONENTS section 6.
- **Plan A keys and TLS stay outside Google:** Trustee on the reference machine as key broker (manual unlock when offline), TLS
  ends inside the VM, no Secret Manager for app secrets. Host order: confidential CPU model server, then the reference machine,
  then an encrypted queue. Rejected: Google load balancer; a confidential GPU server by default (about $10+/h).
  Source: [PLAN-A](../plans/PLAN-A-CLOUD-LED.md) section 8.
- **Plan B ships owner mode first; edge mode later uses a TCP relay that terminates nothing.** Source: PLAN-B B-D1.
- **Native services are the default runtime; Harbor is optional and not installed.** A first draft made Harbor the
  installer and was reverted. Source: `00295bc`, `59e2d4b`, PLAN-B B-D5.
- **Edge mode is supervised by Task Scheduler (systemd on Linux); the pid-file manager stays for owner mode.** Why:
  edge services must run before sign-in. Source: `08d77d7`, PLAN-B B2b.
- **One scheduled task per service, with a 2-minute repeating watchdog trigger (IgnoreNew); `tasks stop` disables the
  task.** Why: Task Scheduler's restart on failure did not restart a killed supervisor within 2.5 minutes. Default
  trigger is `startup` (S4U, elevated); `logon` registers without elevation. Source:
  PR #7, SHARED-COMPONENTS V10.
- **The supervisor joins a kill-on-close job object before it starts the service.** Why: the service tree dies with
  it and there is no spawn-to-assign race. Source: `459904b`, `memory/lessons.md`.
- **Windows dependencies come from a generated winget configuration file**, not from `stack.py setup`. Why:
  unattended, reviewable install. Source: PR #7, SHARED-COMPONENTS V9.
- **Pending (PR #8; done 2026-10-28): per-process CPU, RAM and GPU in the tray** (issue #4, part 2). Source: `28262a1`.

## 2026-10-25

- **A windowless tray app launched through Explorer owns the services; start at login is a Startup-folder shortcut.**
  Why: services must outlive any terminal or agent session. Rejected: starting services from an agent shell with
  `CREATE_BREAKAWAY_FROM_JOB` (tried the same day, unreliable). Source: PR #3,
  [plan](plans/2026-10-25-tray-app.md).
- **Pending (PR #8; done 2026-10-28): services run in a hidden console (`CREATE_NO_WINDOW`).** Why: closing a visible console killed a
  server. Source: `d259e76`.
- **Start uv tools through their environment's `python.exe`**, not the `~/.local/bin` launchers; a blocked service
  warns and the batch continues. Why: Smart App Control blocks each unsigned launcher. Source: `memory/lessons.md`.
- **Identify a service by pid plus process start time.** Why: Windows reuses pids and many `uv.exe` run at once.
  Source: `memory/lessons.md`.
- **The reference machine's primary is `qwen3.5:9b` at 32k**; the 35B MoE stays the class default. Why: about 52 tok/s with
  about 17 GB RAM free, against about 25 tok/s with about 1 GB free. Source: `memory/state.md` benchmarks.
- **The MoE class sends `use_mmap: true` and Ollama gets a 15-minute load timeout.** Why: Ollama disables mmap on
  Windows+CUDA and the load timed out. Source: [ORCHESTRATOR-DESIGN.md](../ORCHESTRATOR-DESIGN.md) section 6.
- **Tiers that share an Ollama model use the same `num_ctx` and load options.** Why: otherwise Ollama reloads on every
  tier switch. Source: `memory/lessons.md`.
- **LiteLLM 1.106.3 (pinned) is the gateway, one complexity router per department; the custom router is removed.**
  Why: a hand-rolled proxy broke tool-using clients. Rejected: custom FastAPI router, Modelfiles, Docker stack.
  Source: PR #2, ORCHESTRATOR-DESIGN section 2.
- **Departments are defined once in `agents/*.yaml` and generated into every tool.** Why: duplicated prompts drifted.
  Source: PR #2.
- **Machine profiles in `machines/`** (hardware class plus host overrides; `doctor --write-profile` adds a host).
  Source: ORCHESTRATOR-DESIGN section 4.
- **Self-development is human-gated**: retro proposes, an eval gate must not regress, the owner merges. Rejected:
  nightly auto-merge; long autonomous sessions. Source: ORCHESTRATOR-DESIGN sections 9-10.

## 2026-10-24

- **Native services, no Docker or WSL2.** Source: [ADR](../decisions/2026-10-24-native-services-no-docker.md).
- **Ollama is the only local inference engine.** Source: [ADR](../decisions/2026-10-24-ollama-only-inference.md).
- **Reuse existing agent harnesses** (Claude Code, OpenCode, Open WebUI) instead of building one; the 2025 design is
  archived. Source: ORCHESTRATOR-DESIGN sections 1 and 3, [archive/DESIGN-2025.md](../archive/DESIGN-2025.md).
- **Claude Code stays on the subscription (profile A); profile B points it at the gateway for owner use.** Source:
  ORCHESTRATOR-DESIGN section 8.
- **Heuristic complexity classifier (no model call); the adaptive router waits for Postgres.** Source:
  ORCHESTRATOR-DESIGN section 7.
- **Cloud tiers resolve to `local-primary` when no API key is set; Fable is never auto-routed.** Superseded by
  2026-10-26 (private first). Source: ORCHESTRATOR-DESIGN section 5.
- **Gateway and orchestrator bind to 127.0.0.1 with bearer tokens from `.env`**; security and code-review agents
  cannot edit. Source: ORCHESTRATOR-DESIGN section 11.
- **Name the orchestrator secret `ORCHESTRATOR_BEARER`.** Why: Claude Code blanks `*_TOKEN` and `*_API_KEY` in
  `.mcp.json`. Source: `memory/lessons.md`.
- **Never send `temperature`, `top_p` or `top_k` to Claude models.** Why: HTTP 400 since 2026-10-21. Source: AGENTS.md rule 3.
- **Short stable AGENTS.md; mutable state in `memory/state.md`, append-only lessons in `memory/lessons.md`.** Source:
  ORCHESTRATOR-DESIGN sections 3 and 8.
- **Run `stack.py doctor` before trusting a handoff.** Why: the 2026-10-24 handoff claimed Ollama, Docker and Open
  WebUI were installed; none were. Source: `memory/lessons.md`.

## Earlier

- 2026-06-07: local-first router with cloud escalation by token count and keyword, in Docker Compose
  (PR #1). Superseded by 2026-10-25 (LiteLLM gateway).
- 2026-05-02: the "Deep-Architect" design, with a message bus and an Ollama adapter. Superseded by 2026-10-24
  (archived in [archive/DESIGN-2025.md](../archive/DESIGN-2025.md)).
