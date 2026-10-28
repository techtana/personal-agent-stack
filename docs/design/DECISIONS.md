# Design decisions

Running log, newest first. Never delete an entry; mark a reversed one "Superseded by <date>". Each line gives the
date, the decision, why, the alternatives turned down, and where it came from. Decisions recorded in more detail
elsewhere link there. Architecture decision records (ADR format) live in [../decisions/](../decisions/README.md).

"Pending" marks a decision made in an open pull request that is not on `main` yet.

## 2026-10-27

- **Tray window has Overview, Usage and Settings tabs.** Settings writes only the changed keys of
  `machines/<HOST>.yaml` (comments kept), rebuilds, and restarts only what the change affects. Why: the owner wanted
  to change settings and see usage per model without editing YAML or reading traces. Source: [PR #9](https://github.com/techtana/personal-agent-stack/pull/9),
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
- **Pending (PR #8): the gateway build is private only.** Routers, fallbacks and defaults name private deployments
  only; the build fails on an external target and refuses `external.enabled: true` until the privacy gate exists.
  Why: enforce private first in generated config, not only in docs. Rejected: `cloud.enabled: auto` (PR #2).
  Source: [PR #8](https://github.com/techtana/personal-agent-stack/pull/8), SHARED-COMPONENTS S6.
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
  measured at about 0.5 GB on SEKAIHOME. Rejected: Authentik on Windows; a custom invite service. Source:
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
- **Plan A keys and TLS stay outside Google:** Trustee on SEKAIHOME as key broker (manual unlock when offline), TLS
  ends inside the VM, no Secret Manager for app secrets. Host order: confidential CPU model server, then SEKAIHOME,
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
  [PR #7](https://github.com/techtana/personal-agent-stack/pull/7), SHARED-COMPONENTS V10.
- **The supervisor joins a kill-on-close job object before it starts the service.** Why: the service tree dies with
  it and there is no spawn-to-assign race. Source: `459904b`, `memory/lessons.md`.
- **Windows dependencies come from a generated winget configuration file**, not from `stack.py setup`. Why:
  unattended, reviewable install. Source: PR #7, SHARED-COMPONENTS V9.
- **Pending (PR #8): per-process CPU, RAM and GPU in the tray** (issue #4, part 2). Source: `28262a1`.

## 2026-10-25

- **A windowless tray app launched through Explorer owns the services; start at login is a Startup-folder shortcut.**
  Why: services must outlive any terminal or agent session. Rejected: starting services from an agent shell with
  `CREATE_BREAKAWAY_FROM_JOB` (tried the same day, unreliable). Source: [PR #3](https://github.com/techtana/personal-agent-stack/pull/3),
  [plan](plans/2026-10-25-tray-app.md).
- **Pending (PR #8): services run in a hidden console (`CREATE_NO_WINDOW`).** Why: closing a visible console killed a
  server. Source: `d259e76`.
- **Start uv tools through their environment's `python.exe`**, not the `~/.local/bin` launchers; a blocked service
  warns and the batch continues. Why: Smart App Control blocks each unsigned launcher. Source: `memory/lessons.md`.
- **Identify a service by pid plus process start time.** Why: Windows reuses pids and many `uv.exe` run at once.
  Source: `memory/lessons.md`.
- **SEKAIHOME's primary is `qwen3.5:9b` at 32k**; the 35B MoE stays the class default. Why: about 52 tok/s with
  about 17 GB RAM free, against about 25 tok/s with about 1 GB free. Source: `memory/state.md` benchmarks.
- **The MoE class sends `use_mmap: true` and Ollama gets a 15-minute load timeout.** Why: Ollama disables mmap on
  Windows+CUDA and the load timed out. Source: [ORCHESTRATOR-DESIGN.md](../ORCHESTRATOR-DESIGN.md) section 6.
- **Tiers that share an Ollama model use the same `num_ctx` and load options.** Why: otherwise Ollama reloads on every
  tier switch. Source: `memory/lessons.md`.
- **LiteLLM 1.106.3 (pinned) is the gateway, one complexity router per department; the custom router is removed.**
  Why: a hand-rolled proxy broke tool-using clients. Rejected: custom FastAPI router, Modelfiles, Docker stack.
  Source: [PR #2](https://github.com/techtana/personal-agent-stack/pull/2), ORCHESTRATOR-DESIGN section 2.
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
  ([PR #1](https://github.com/techtana/personal-agent-stack/pull/1)). Superseded by 2026-10-25 (LiteLLM gateway).
- 2026-05-02: the "Deep-Architect" design, with a message bus and an Ollama adapter. Superseded by 2026-10-24
  (archived in [archive/DESIGN-2025.md](../archive/DESIGN-2025.md)).
