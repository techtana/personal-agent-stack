# Shared components for Plan A (cloud-led) and Plan B (local-led)

Revised 2026-10-26 (private-first): every request runs on private models by default. External model APIs are off at
install. When enabled, they are a deliberate, last-resort user choice, and the privacy gate still applies with no
override. No add-ons are offered for clients outside the privacy boundary. Harbor is an optional runtime; the
orchestrator and the planned MCP server are dropped. Where an established open-source tool already does a job
(Presidio, detect-secrets, deface, mat2, LiteLLM access groups and logs, winget configure, Trustee, Authentik,
Keycloak), the plans use it and write only the glue and the rules no tool provides; section 7 lists what remains to
verify. Dependencies and configuration steps: `INSTALL.md`.

Effort sizes: S = up to 1 day, M = 2-3 days, L = 4-6 days, for one developer working with the department agents.

## 0. Principles

1. **Private first.** Every department, every complexity tier, embeddings, titles and media run on private models.
   Private means one of:
   - hardware we own (SEKAIHOME, an office server), or
   - a confidential cloud VM in our own project: memory encrypted by the CPU (AMD SEV-SNP or Intel TDX, plus NVIDIA
     confidential computing on GPU hosts), checked by remote attestation, with disks and backups encrypted under keys
     the cloud provider does not hold (Plan A).
2. **External models are optional and intentional.** Anthropic API, Vertex AI, Hugging Face, OpenRouter and every other
   third-party API are disabled at install. An admin can enable them for chosen groups; a user then has to opt in, pick
   an external model by name, and confirm per conversation. No router tier, fallback, default, task model, queue or
   automatic escalation ever sends anything to an external model.
3. **The gate is not optional.** Every request to an external model is checked locally first. Sensitive content is
   refused, with no user or per-request admin override. If the gate is unhealthy, external models are unavailable.
4. **One privacy boundary, stated plainly.**

| Inside the boundary (enforced) | Owner development tool (gated, not a user surface) | Outside the boundary (no integration on purpose) |
|---|---|---|
| Open WebUI, locked down by the installer; open-source clients whose only model endpoint is the gateway (OpenCode, Continue), configured by the build | Claude Code profile B (`claude-local`): model calls go through the gateway and the gate, with non-essential traffic disabled and web tools denied. The client itself is proprietary, so it is not part of the promise made to users. | Claude Code on a subscription (profile A), Claude Desktop, vendor chat apps, any client that talks to its own cloud. The project ships no skills, hooks or MCP add-ons for them: an add-on there could only advise, and would suggest a protection that does not exist. |

5. **Fail closed, log no content, detect locally.** A gate error, timeout or missing verdict counts as sensitive.
   Verdicts, audit rows and traces hold categories and counts, never the matched text. All detection runs on our own
   hardware or confidential VMs, on CPU.

## 1. Data classes and private tiers

Every model deployment in the generated LiteLLM config carries `model_info.data_class` (`private` or `external`) and,
for private ones, `model_info.location` (`onprem` or `confidential-cloud`). The build fails if one is missing.

Department aliases (`<dept>`) are complexity routers over private deployments only:

| Tier | Plan A | Plan B |
|---|---|---|
| simple, medium | `private-small` / `private-primary` on the confidential model server, then on-prem | local `<dept>-local` |
| complex, reasoning | `private-large` where a host can serve one (confidential GPU option or a larger on-prem model), else `private-primary` | local `<dept>-local`, or a larger local model when one is pulled |
| media | private vision deployment | local vision deployment |
| embeddings | `private-embed` (privacy-gate) | `private-embed` |

Optional policy: `special_categories_location: onprem` keeps special-category data on owned hardware even when a
confidential cloud host is available.

## 2. External access policy (both plans)

| Control | Rule |
|---|---|
| Default | `external.enabled: false` in `policy/privacy.yaml`; the build emits no external deployments while it is false |
| Naming | external models exist only as explicit aliases, for example `external/anthropic/claude-sonnet-5-5`, shown in Open WebUI as "External · Anthropic · Claude Sonnet 5.5" with a warning badge |
| Reachability | never referenced by a router tier, fallback, default, task model, embeddings, queue replay or "(private)" model; the build checks this and fails otherwise |
| Who | external aliases sit in a LiteLLM model access group `external`; only users an admin adds to the `external` group (mapped by a LiteLLM `custom_auth` function, V2) can call them, and each user must also turn on "Allow external models" in their own settings |
| When | the first message of a conversation to an external model opens a confirmation dialog naming the provider and stating what will be sent; declining stops the request. The consent (user, chat, provider, time) is stored by privacy-gate; the hook refuses an external request without a matching consent |
| What | the gate checks the whole request; sensitive -> refused with the categories named and a one-click resend to the private model (`external_on_sensitive: refuse`). Optional `generalize` (off by default, admin-enabled per category): the user sees a local rewrite without personal details and decides whether to send that |
| Identity | one shared provider key; no user id, email, name, forwarded headers or `user` field reaches a provider; Open WebUI memories and user variables are part of the checked text |
| Retention | provider options that limit retention and training are switched on where offered, recorded per provider at install |
| Gate down | external aliases refuse every request |
| Audit | every external request in LiteLLM's request log (PostgreSQL, prompts not stored): user, provider, model, tokens; verdict categories as request metadata |

## 3. What the gate protects against

Two risks: one request exposing something sensitive, and many harmless-looking requests letting a provider profile a
person. In this design the gate decides only what may go external; everything stays private by default anyway.

| Group | Categories |
|---|---|
| Direct identifiers | names with context, email, phone, postal address, government and account numbers, payment cards, IBAN, usernames and handles, device IDs, IP and MAC addresses (opt-in), licence plates |
| Quasi-identifiers | age or birth date, small-area location, employer and job title, school, nationality; two or more about one person count as sensitive |
| Special categories | health and mental health; sex life, sexual orientation and gender identity; racial or ethnic origin; religious or philosophical beliefs; political opinions; trade-union membership; genetic and biometric data; criminal records |
| Profilable personal context | personal interests and lifestyle (hobbies, routines, habits, memberships); family and relationships; precise location and movement patterns; personal finances; employment and HR matters; children and minors; private messages from or about other people |
| Secrets and confidential | keys, tokens, passwords, connection strings; organisation terms and customer lists |
| Media | faces, people or bodies, nudity, identity documents and screens with personal text, location metadata (EXIF GPS), voices |

**Personal-disclosure rule.** Topic categories count only when they are about a person (first person, or an
identified or identifiable person). "How do I true a bicycle wheel" is not sensitive; "I ride every Saturday at 6
from the park next to my flat" is.

## 4. Work packages

### S1. `privacy-gate`: detection built on existing tools (L)

`packages/privacy-gate/` (own `pyproject.toml`, uv workspace member; also built as a container image). Its own code
is the glue and the rules in the last three rows; everything else is configuration of existing tools.

| Detector | Tool | Our part |
|---|---|---|
| identifiers (email, phone, cards with Luhn, IBAN, national IDs, IPs, URLs) | **Microsoft Presidio Analyzer** predefined recognizers | which recognizers and regions are on (G1); extra national-ID pattern recognizers in YAML |
| names, places, organisations | Presidio NLP engine (small spaCy models such as `en_core_web_sm` plus `xx_ent_wiki_sm`; not Presidio's default `en_core_web_lg`, which alone exceeds 900 MB: V4) | model choice and languages |
| org terms, customer list | Presidio deny-list and pattern recognizers, loaded from `policy/` | the lists |
| secrets | **detect-secrets** plugins (keys, tokens, private keys, high-entropy strings); gitleaks rules as an alternative | which plugins are on |
| disclosure | ours: first-person and identified-person cues on top of Presidio's entities | yes |
| quasi-identifier combiner | ours: two or more quasi-identifiers linked to one person | yes |
| special categories and profilable context | ours: multilingual ONNX sentence embeddings (`fastembed`) against exemplars in `policy/topics/*.yaml`; compared in the S1 test with LLM Guard's BanTopics (zero-shot, heavier) | yes |

**S1b media (M), assembled from existing tools** (licences recorded in `packages/privacy-gate/MODELS.md`):

| Input | Tools |
|---|---|
| image | **mat2** (Linux) or ExifTool (Windows, V11) reports metadata (EXIF GPS, device, author); **deface** detects faces (CenterFace); **Presidio Image Redactor** finds personal text through OCR (ID cards, screenshots); a permissively licensed nudity classifier (not NudeNet, which is AGPL-3.0: V5); a small permissive person detector (RT-DETR, Apache-2.0) |
| video | `ffmpeg` samples 1 frame per second plus scene changes (max 120) for the image pipeline; **deface** also handles video directly; the audio track counts as voice |
| audio | voice is biometric, so sensitive; optional local transcription (whisper.cpp) to scan the words |
| documents | text extraction plus the image pipeline for embedded images; **mat2** for document metadata |
| anything else | `unscannable`, so sensitive |

**S1c redaction (S):** **Presidio Anonymizer** (text), **deface** (blur faces in images and video), **Presidio Image
Redactor** (personal text in images), **mat2** (strip metadata); the result is scanned again. Used only by the
optional admin-enabled `generalize` / `redact` steps before an intentional external send.

Verdict (no matched text): `{"sensitive", "categories", "reasons", "score", "scanned", "cached_parts", "ms",
"gate_version"}`. Targets: text p95 <= 50 ms for 4k new tokens, <= 400 ms for 32k; image p95 <= 300 ms; video <= 20 s
per minute; resident memory <= 900 MB with the media models loaded on demand. Parts cached by SHA-256 (hashes only,
LRU 10k, 24 h).

### S2. Gate service (M)

`privacy-gate`, internal only, bearer `GATE_BEARER`:

| Endpoint | Purpose |
|---|---|
| `POST /v1/classify` | messages, text or file references -> verdict |
| `POST /v1/redact`, `POST /v1/generalize` | S1c; `generalize` uses the private chat model |
| `POST /v1/embeddings` | OpenAI-compatible, served by the topic model (`private-embed`) |
| `POST /v1/consent`, `GET /v1/consent` | external-model consents (section 2) |
| `GET /v1/private-status` | availability of each private host |
| `GET /healthz` | liveness; the LiteLLM guardrail refuses external requests when it fails |

Plan A adds the deferred queue and the model-server start/stop controller to this service.

### S3. LiteLLM enforcement (S)

Mostly LiteLLM's own features, plus one small custom guardrail:

| Need | LiteLLM feature |
|---|---|
| only permitted users reach external models | model access group `external` on the external aliases. A small `custom_auth` function checks Open WebUI's dedicated key, reads the forwarded `X-OpenWebUI-User-Email`, and returns that user's allowed groups (`private`, plus `external` for granted users) as `models`; `litellm_settings.enable_post_custom_auth_checks: true` makes LiteLLM enforce them. The plain `user_header_name` end-user mapping is not used: it fails open (V2) |
| private-only routing | static config from the build (S6): department routers, fallbacks and defaults reference private deployments only |
| request log, spend and routing view | LiteLLM's PostgreSQL request log and admin UI, with prompt and response storage turned off |
| pass-through routes skip hooks | pass-through endpoints not configured; test that `/anthropic/*` and `/vertex_ai/*` return 404 |

Custom guardrail `infrastructure/litellm/privacy_guardrail.py` (a `CustomGuardrail` subclass, mode `pre_call`,
`default_on: true`; native: the LiteLLM uv tool is installed `--with-editable packages/privacy-gate`):
- if the routed model's `data_class` is `external`: require `external.enabled`, the user's opt-in, a matching consent
  and a non-sensitive verdict from `/v1/classify`; otherwise return a refusal as the assistant reply; strip user
  identifiers;
- private models pass without a call to the gate (they are private by construction);
- a final `async_pre_call_deployment_hook` check raises `PrivacyViolation` if a request is ever about to reach an
  external deployment without a passing verdict (defence in depth against configuration mistakes). It reads the
  chosen deployment from `kwargs["model_info"]` and raises a non-retryable 4xx error, since a plain exception becomes
  a 500 that the router retries (V1).

Plan A adds credential injection for the confidential model server to the same class.

### S4. Open WebUI integration (M)

Built-in features do most of it:
- **Groups and per-model access control** hide external models from everyone outside the `external` group.
- **Settings** applied by the installer: one connection (LiteLLM); direct connections off; task model, RAG
  embeddings and title generation on private aliases; web search and image generation off; community imports off;
  user-info headers forwarded to LiteLLM for attribution and consent (never to providers):
  `ENABLE_FORWARD_USER_INFO_HEADERS=true`, no `FORWARD_USER_INFO_HEADER_JWT_SECRET`, and a dedicated LiteLLM key that
  only Open WebUI holds. Consent is keyed on `X-OpenWebUI-Chat-Id`; calls without one fall back to per user for 30
  minutes (V3).
- **Feedback** (thumbs, comments) stays in Open WebUI and feeds `retro`.

Ours: one filter function, `config/openwebui/functions/privacy_notice.py`. For external models it checks the user's
opt-in, shows the consent dialog (`__event_call__` confirmation) on the first message of a conversation, records the
consent through `/v1/consent` and shows the verdict. For private models it shows status notices ("starting the
private server", "queued", "image processed privately"). Plan A's queue status reaches users through these notices and
an email; there is no separate tool.

### S5. MCP server: dropped

Every client inside the boundary already passes through the gateway and the guardrail, so check/redact tools added
nothing for users, and the queue status moved to filter notices and email. No MCP server, skill, hook or `.mcp.json`
entry is built for privacy (principle 4).

### S6. Build changes (M)

`scripts/stacklib/litellm_build.py`, `agents_build.py`:
- replace `cloud.enabled: auto` (today a configured `ANTHROPIC_API_KEY` sends complex tiers to Anthropic) with
  `external.enabled: false` and explicit external aliases in the `external` access group; department routers over
  private deployments only;
- provider-qualified external models (`anthropic/…`, `vertex_ai/…`, `huggingface/…`, `openai/…` with `api_base`); no
  temperature for Anthropic (AGENTS.md rule 3);
- `data_class` and `location` on every deployment; static check that no router tier, fallback, default, task model or
  embedding alias references an external deployment;
- `general_settings`: `database_url`, `user_header_name`, prompt storage off in request logs; the guardrail entry;
- Claude Code profile B: aliases point only at private models; the generated env sets
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`; the profile denies `WebFetch` and `WebSearch`;
- write the gate config, the Open WebUI assets, `winget/configuration.winget` (INSTALL.md) and, for `compose`,
  `infrastructure/compose/<deployment>.yaml`.

### S7. Identity on an existing identity provider (M)

No custom invite service. Both candidates provide TOTP, passkeys, OIDC for Open WebUI, invitations and an admin view
of users:

| | Plan A: **Authentik** (inside the confidential main VM, containers) | Plan B: **Keycloak** (native on Windows through Java, or Linux) |
|---|---|---|
| Authenticator app (TOTP) required at first sign-in | enrollment flow with a TOTP setup stage | required action "Configure OTP" |
| Passkey per device | WebAuthn stage | passkeys (officially supported since 26.4) |
| Per-device sessions and sign-out | user's session list | account console "Device activity" with per-session sign-out |
| Invite -> admin approval | invitation stage in an enrollment flow; users created inactive until an admin activates them | admin-sent invitations (organizations) or registration with accounts disabled until an admin enables them |
| Brute force | reputation policies | brute-force detection |
| Runs on | Linux containers | JVM on Windows or Linux |

Common rules, configured rather than coded: sessions 12 h idle / 7 d absolute for users and 1 h / 12 h for admins;
admins passkey-only with one break-glass account sealed offline; invite rights are a group with a cap per inviter;
optional allow-list of email domains; mail through an SMTP relay on port 587; Open WebUI uses the provider over OIDC
with its login form and signup off and new users `pending`; groups claim mapped to Open WebUI groups. Roles: admin,
member, pending, plus the `external` group from section 2.

### S8. Evaluation and release gate (M)

`evals/privacy-gate/`, synthetic data only:
- text positives and negatives generated with **presidio-evaluator** (fake personal data in templates) plus
  hand-written cases for the profiling rules: >= 40 positives per category in section 3 per configured language,
  >= 300 negatives from ordinary coding, docs and devops work; a media set with and without faces, people, documents
  and GPS data (no photos of real people without consent); presidio-evaluator also reports per-entity recall;
- **leak canary** (ours): a mock external provider records everything it receives. With `external.enabled: false` it
  must receive nothing. With it enabled, it must receive no sensitive positive on any route, nothing without consent,
  nothing from a user outside the `external` group, nothing while the gate is down, nothing through a fallback, and no
  user identifiers;
- static check from S6.

Release gate (`stack.py gate-eval`, CI): recall >= 0.98 for secrets, identifiers and media; >= 0.90 for special
categories and profilable context; false positives <= 10 %; latency and memory targets from S1; leak canary 0.

## 5. Removed (package R, once the privacy-gate service runs)

| Remove | Replaced by |
|---|---|
| `orchestrator/` (server, jobs store, Dockerfile), `ORCHESTRATOR_BEARER`, its entry in `services.py` and the tray, `.mcp.json` and `enabledMcpjsonServers`, smoke's orchestrator check | departments as LiteLLM aliases and Open WebUI models; privacy-gate takes the orchestrator's place in the service list |
| `record_lesson` tool | agents append to `memory/lessons.md` directly |
| Automatic cloud tiers (`cloud.enabled: auto`, `default_fallbacks` and `context_window_fallbacks` to `cloud-*`) | private-only routers; explicit external aliases (S6) |
| Phoenix (uv tool, service entry, OTel callback, tray link) | LiteLLM request log and admin UI |
| `infrastructure/litellm/custom_callbacks.py` (JSONL traces with prompt text), `scripts/stacklib/traces.py`, `stack.py why-routed` and its skill | LiteLLM's PostgreSQL request log and admin UI (no prompt storage); `retro` reads the request log and Open WebUI feedback |
| `scripts/hooks/log_turn.py` and its Claude Code hooks | Claude Code's built-in OpenTelemetry export to a local collector, if the owner wants development traces |
| Dependency installs inside `stack.py setup` | `winget configure` on Windows, Terraform and cloud-init on Linux; `setup` keeps databases, model pulls and the build |
| `infrastructure/docker-compose.yml` (untested) | generated `infrastructure/compose/<deployment>.yaml` |
| README, AGENTS.md and `docs/ORCHESTRATOR-DESIGN.md` sections on the above | rewritten; `memory/lessons.md` keeps its history |

Kept: the native runtime for `owner` mode (`services.py`, `startup.py`, `tray.py`, `stack.py up/down/status/tray/pull`;
shared or multi-user hosts move supervision to Task Scheduler or systemd, Plan B package B2b), `agents/*.yaml` and
the build, `machines/*.yaml` and `doctor`, `bench`, `smoke` (retargeted), `retro`, evals.

## 6. Shared decisions (defaults used unless changed)

| # | Decision | Default |
|---|---|---|
| G1 | Regions for identifier validators, languages for NER and topics | US and English; add others before go-live |
| G2 | NER, topic, person and nudity models | chosen in the S1 test; permissive licences only |
| G3 | External models | disabled |
| G4 | `generalize` / `redact` before an intentional external send | disabled |
| G5 | Special categories allowed on confidential cloud hosts | yes (`special_categories_location: any`); set `onprem` to keep them on owned hardware |
| G6 | Users or admins may override a sensitive verdict per request | never |
| G7 | Topic detector | our embedding exemplars, unless LLM Guard BanTopics scores better within the memory target |

## 7. To verify before building on it

| # | Item | Checked in | Result (2026-10-26) |
|---|---|---|---|
| V1 | LiteLLM guardrails cannot be scoped per model in the docs found (global, per key, per request); the guardrail therefore checks the routed model's `data_class` itself. Confirm `async_pre_call_deployment_hook` sees the chosen deployment in LiteLLM 1.106.3 | S3 | **Confirmed** (source and a test proxy). The hook runs after routing and fallback selection, before the provider call, on both `/v1/chat/completions` and `/v1/messages`; `kwargs["model_info"]` is the chosen deployment's. Raising blocks the call. A `guardrails:` list under a deployment's `litellm_params` also scopes a guardrail per model. Keep the global callback (a config typo cannot skip it) and raise a non-retryable 4xx: a plain exception returns 500 and the router retries it three times |
| V2 | LiteLLM model access groups work with end users identified by Open WebUI's forwarded user header (not only with virtual keys) | S3 | **Refuted as stated.** `user_header_name` only sets `end_user_id`; without Postgres the end-user lookup fails and the request passes unrestricted (fails open, logged at debug only). With Postgres, customer model limits apply. Without a DB, a `custom_auth` function that maps the forwarded email to `models: [<access groups>]` plus `litellm_settings.enable_post_custom_auth_checks: true` enforces it (tested: 403 `key_model_access_denied`); without that flag only `/v1/models` is filtered. JWT auth is enterprise-only. The header is trusted only when Open WebUI holds a dedicated key that `custom_auth` checks |
| V3 | Open WebUI forwards the chat id to LiteLLM; otherwise consent is per user for 30 minutes | S4 | **Confirmed with gaps** (Open WebUI 0.12.3 source). Needs `ENABLE_FORWARD_USER_INFO_HEADERS=true`; sends `X-OpenWebUI-Chat-Id` plus user id, email, name and role headers (names configurable). Title, tag and tool-selection task calls carry the chat id; temporary chats send `temporary:<session>`. Missing for API calls without `chat_id`; message id only through a connection header template (`{{MESSAGE_ID}}`). Setting `FORWARD_USER_INFO_HEADER_JWT_SECRET` replaces the plain user headers with one signed JWT. Keep the per-user 30-minute fallback for calls without a chat id |
| V4 | Presidio NER model and languages fit the 900 MB memory target together with the topic model | S1 | **Confirmed for small models** (measured on SEKAIHOME; presidio-analyzer 2.2.365, spaCy 3.8, torch 2.14 CPU). Steady RSS: Presidio + `en_core_web_sm` 394-435 MB (7 ms per text); plus `xx_ent_wiki_sm` 680 MB; plus a zero-shot topic model 546-669 MB; sm + xx + DeBERTa-v3-xsmall zero-shot + detect-secrets 821 MB. Over target: Presidio's default `en_core_web_lg` alone 978 MB; transformers NER (`dslim/bert-base-NER`) + zero-shot 899 MB. Zero-shot topic models take 0.56-2.9 s per text with five labels, far over the 50 ms text target, so G7's embedding exemplars stay the default and BanTopics is only a comparison. detect-secrets adds no measurable memory but needs filters (191 raw hits on 20 texts). Install paths must stay short or enable Windows long paths: spaCy and the Hugging Face cache failed past 260 characters |
| V5 | Licences: deface (and its CenterFace model), NudeNet, any person detector, Presidio Image Redactor's OCR engine (Tesseract) | S1b | **Partly.** deface and CenterFace: MIT. Tesseract and tessdata_fast: Apache-2.0. Presidio: MIT. **NudeNet v3: AGPL-3.0** (YOLOv8-based weights), so it is out under G2. Person detector: RT-DETR (`PekingU/rtdetr_r18vd`, Apache-2.0, via transformers); MediaPipe model files have no stated licence. Nudity classifier still to choose |
| V6 | Authentik: enrollment flow with an invitation stage and users created inactive pending admin activation | S7 (Plan A) | **Confirmed** (docs 2026.8): Invitation stage (turn off "Continue flow without invitation") plus User Write stage "Create users as inactive", then admin activation. Admins and users can end single sessions; admins remove single MFA devices |
| V7 | Keycloak: runs as a native Windows service on SEKAIHOME within the RAM budget; device activity with per-session sign-out; invitation plus admin enablement flow | S7 (Plan B, B-S0) | **Docs part mostly confirmed** (26.8.1, OpenJDK 25): official Windows service through `kc.bat tools windows-service install` (Apache Commons Daemon); account console device activity with per-device sign-out; organization invitations (use at least 26.7.3, CVE-2026-16072). Self-registered users cannot be created disabled without an extension. Memory: the sizing guide's baseline is about 1.25 GB; plan 1.3-1.5 GB. Runtime test on SEKAIHOME not run (B-S0) |
| V8 | Trustee (KBS + Attestation Service) on Google Cloud Confidential VMs (SEV-SNP, TDX) releasing a LUKS key at boot; the systemd disk-key integration is a 2026 proposal, not a shipped feature | Plan A, A-S0 | **Partly.** Trustee has plain `snp` and `tdx` verifiers (the `az_*` vTPM ones are Azure-only); no documented GCP test. No shipped boot-time client: clevis-pin-trustee has no release and the systemd-cryptsetup token is still a proposal. A-S0 must budget a custom initramfs hook (attester plus KBS fetch); Clevis + Tang stays the fallback |
| V9 | `winget configure` installs every Windows dependency unattended, and Smart App Control allows each installed binary | INSTALL, B3 | Not run (changes SEKAIHOME; B-S0) |
| V10 | Task Scheduler start at boot and restart on failure for the native services | Plan B, B2b | Not run (changes SEKAIHOME; B2b) |
| V11 | mat2 does not run natively on Windows; ExifTool covers metadata there. Confirm ExifTool reads and strips the formats Open WebUI accepts | S1b, Plan B | **Partly** (ExifTool 13.59). Writes JPEG, PNG, WebP, GIF, HEIC, MP4, MOV and PDF; **read-only for DOCX/XLSX/PPTX, MP3 and WAV**. PDF edits are incremental, so old data stays until `qpdf --linearize`. mat2 (LGPL-3.0) covers all of them but needs WSL or Linux. On Windows without WSL: ExifTool plus qpdf, with Office and audio metadata stripped by small Python code (zip `docProps`, mutagen) or those uploads blocked |
