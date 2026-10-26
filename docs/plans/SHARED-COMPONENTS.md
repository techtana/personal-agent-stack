# Shared components for Plan A (cloud-led) and Plan B (local-led)

Revised 2026-10-26 (private-first): every request runs on private models by default. External model APIs are off at
install. When enabled, they are a deliberate, last-resort user choice, and the privacy gate still applies with no
override. No add-ons are offered for clients outside the privacy boundary. Harbor is an optional runtime; the
orchestrator is removed. Dependencies and configuration steps: `INSTALL.md`.

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
| Who | groups an admin grants `external`; each user must also turn on "Allow external models" in their own settings |
| When | the first message of a conversation to an external model opens a confirmation dialog naming the provider and stating what will be sent; declining stops the request. The consent (user, chat, provider, time) is stored by privacy-gate; the hook refuses an external request without a matching consent |
| What | the gate checks the whole request; sensitive -> refused with the categories named and a one-click resend to the private model (`external_on_sensitive: refuse`). Optional `generalize` (off by default, admin-enabled per category): the user sees a local rewrite without personal details and decides whether to send that |
| Identity | one shared provider key; no user id, email, name, forwarded headers or `user` field reaches a provider; Open WebUI memories and user variables are part of the checked text |
| Retention | provider options that limit retention and training are switched on where offered, recorded per provider at install |
| Gate down | external aliases refuse every request |
| Audit | every external request: user, provider, model, size, verdict (no content) |

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

### S1. `privacy-gate`: detectors (L)

`packages/privacy-gate/` (own `pyproject.toml`, uv workspace member; also built as a container image).

| Detector | Method |
|---|---|
| secrets | regex set plus entropy checks |
| identifiers | regex plus validators (`phonenumbers` per configured region, Luhn, IBAN mod-97, national-ID checksums) |
| ner | small multilingual ONNX token-classification model |
| disclosure | first-person and identified-person cues (lexicon plus NER) |
| topics | multilingual ONNX sentence-embedding model (`fastembed`) against exemplars in `policy/topics/*.yaml`; max over 512-token chunks |
| quasi-identifier combiner | two or more quasi-identifiers linked to one person |
| org_terms | literal terms, regexes, customer list |

**S1b media (M)**, ONNX on CPU, permissive licences recorded in `packages/privacy-gate/MODELS.md`: image (EXIF ->
faces -> people -> nudity -> OCR text through the text detectors); video (`ffmpeg`, 1 frame per second plus scene
changes, max 120 frames, audio counts as voice); audio (voice is biometric; optional local transcription); documents
(text plus embedded images); anything else `unscannable` (sensitive).

**S1c redaction (M):** masks text spans; blurs faces, people and OCR regions; strips metadata; re-scans the result.
Used only by the optional admin-enabled `generalize` / `redact` steps before an intentional external send.

Verdict (no matched text): `{"sensitive", "categories", "reasons", "score", "scanned", "cached_parts", "ms",
"gate_version"}`. Targets: text p95 <= 50 ms for 4k new tokens, <= 400 ms for 32k; image p95 <= 300 ms; video <= 20 s
per minute; resident memory <= 900 MB. Parts cached by SHA-256 (hashes only, LRU 10k, 24 h).

### S2. Gate service (M)

`privacy-gate`, internal only, bearer `GATE_BEARER`:

| Endpoint | Purpose |
|---|---|
| `POST /v1/classify` | messages, text or file references -> verdict |
| `POST /v1/redact`, `POST /v1/generalize` | S1c; `generalize` uses the private chat model |
| `POST /v1/embeddings` | OpenAI-compatible, served by the same ONNX model (`private-embed`) |
| `POST /v1/consent`, `GET /v1/consent` | external-model consents (section 2) |
| `GET /v1/private-status` | availability of each private host |
| `/mcp` | MCP server for Open WebUI and gateway-routed open-source clients (S5) |
| `GET /healthz` | liveness; LiteLLM disables external aliases when it fails |

Plan A adds the deferred queue and the model-server start/stop controller to this service.

### S3. LiteLLM enforcement hook (M)

`infrastructure/litellm/privacy_hook.py` (native: LiteLLM uv tool installed `--with-editable packages/privacy-gate`;
containers: mounted). Three layers:

1. `async_pre_call_hook`: classify the full request (system prompt, messages, tool results, images and files,
   embeddings `input`). For an external alias: require `external.enabled`, the user's group grant and opt-in, a
   matching consent and a non-sensitive verdict; otherwise return a refusal as the assistant reply (LiteLLM
   `RejectedRequestError`). Strip user identifiers before any external call. For private aliases: set
   `disable_fallbacks: true` when the private host group is exhausted, and apply `on_private_unavailable`.
2. `async_filter_deployments`: drop every `external` deployment unless the request passed layer 1 for that exact
   external alias; with `special_categories_location: onprem`, drop `confidential-cloud` deployments for those
   categories.
3. `async_pre_call_deployment_hook`: final assertion before sending; raise `PrivacyViolation` and audit on any
   mismatch. Plan A injects credentials for the confidential model server here.

Cover `completion`, `anthropic_messages`, `responses`, `embeddings`, `text_completion`, `image_generation` and audio
transcription. Disable pass-through routes (`/anthropic/*`, `/vertex_ai/*` and similar), which skip hooks. One audit
row per request.

### S4. Open WebUI integration (M)

- **Filter function** `config/openwebui/functions/privacy_notice.py`:
  - for external models: checks the user's opt-in, shows the consent dialog (`__event_call__` confirmation) on the
    first message of a conversation, records the consent through `/v1/consent`, and shows the gate's verdict;
  - for private models: shows status notices ("starting the private server", "queued", "image processed
    privately").
  It informs and collects consent; LiteLLM enforces.
- **Models:** department models are private; external models only for granted groups, labelled "External · …".
- **Settings** applied by the installer: one connection (LiteLLM); direct connections off; task model, RAG embeddings
  and title generation on private aliases; web search and image generation off (each would send data to a third
  party); community imports off; user-info headers forwarded to LiteLLM for attribution only (verify that Open WebUI
  forwards the chat id; otherwise consent is per user and expires after 30 minutes).

### S5. MCP server (S)

Served by privacy-gate over Streamable HTTP, inside the network, for Open WebUI (registered by the installer) and
gateway-routed open-source clients (OpenCode, Continue):

| Tool | Does |
|---|---|
| `check_text`, `check_file`, `check_media` | verdict with plain-language reasons |
| `redact`, `generalize` | only when the admin has enabled them |
| `policy` | categories, actions and the privacy boundary in force |
| `list_deferred`, `get_deferred`, `cancel_deferred` | Plan A queue |

Not provided, by decision on 2026-10-26: skills, Claude Code hooks or `.mcp.json` entries for privacy, a stdio mode
for desktop apps, or any Claude Desktop integration (principle 4).

### S6. Build changes (M)

`scripts/stacklib/litellm_build.py`, `agents_build.py`:
- replace `cloud.enabled: auto` (today a configured `ANTHROPIC_API_KEY` sends complex tiers to Anthropic) with
  `external.enabled: false` and explicit external aliases; department routers over private deployments only;
- provider-qualified external models (`anthropic/…`, `vertex_ai/…`, `huggingface/…`, `openai/…` with `api_base`); no
  temperature for Anthropic (AGENTS.md rule 3);
- `data_class` and `location` on every deployment; static check that no router tier, fallback, default, task model or
  embedding alias references an external deployment;
- Claude Code profile B: `opus_model` and the other aliases may point only at private aliases; the generated env sets
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, and the profile denies `WebFetch` and `WebSearch`;
- load `privacy_hook`; write the gate config and Open WebUI assets; `native`: add privacy-gate to `services.py` and the
  tray; `compose`: write `infrastructure/compose/<deployment>.yaml`.

### S7. Identity (L)

Caddy, Authelia (OIDC provider), LLDAP and a small invite service (`packages/identity-edge/`, own SQLite). Plan A runs
it inside the confidential main VM. Plan B runs it on SEKAIHOME if native Windows builds work (spike B-S0), with the
edge VM as a pure encrypted relay; otherwise on a confidential edge VM.

- **Second factor:** a TOTP authenticator app must be enrolled at first sign-in. Each device registers its own
  passkey (WebAuthn); users list and delete their passkeys. Sessions are per browser: 12 h idle / 7 d absolute for
  users, 1 h / 12 h for admins. A lost device: delete its passkey and reset the password (ends all sessions; Authelia
  has no per-session list). Brute-force bans (Authelia regulation) and rate limits (Caddy).
- **Admins:** passkey required, separate group, one break-glass account sealed offline (its use raises an alert).
- **Invites with approval:** a member submits an email; admins approve (choosing a group) or reject; on approval the
  service creates the LLDAP user and emails a one-time set-password link (72 h); first sign-in forces TOTP then a
  passkey; Open WebUI also keeps new users `pending`. Invite rights are a group permission with a cap per inviter;
  optional allow-list of email domains. Mail through an SMTP relay on port 587.
- **Roles:** admin (approve invites, manage groups, models, hosts, external grants, budgets; read audit log), member
  (allowed departments, own devices and data; invite if permitted; external models only if granted and opted in),
  pending (nothing).
- **Open WebUI:** OIDC client of Authelia; login form and signup off; groups claim mapped to Open WebUI groups.

### S8. Evaluation and release gate (M)

`evals/privacy-gate/`, synthetic data only:
- >= 40 positives per category in section 3 (per configured language), including profiling cases; >= 300 negatives
  from ordinary coding, docs and devops work; a media set with and without faces, people, documents and GPS data (no
  photos of real people without consent);
- **leak canary:** a mock external provider records everything it receives. With `external.enabled: false` it must
  receive nothing at all. With it enabled, it must receive no sensitive positive on any route, nothing without
  consent, nothing from an unpermitted user, nothing while the gate is down, nothing through a fallback, and no user
  identifiers;
- static check from S6 (no external reference in routers, fallbacks, defaults, task or embedding aliases).

Release gate (`stack.py gate-eval`, CI): recall >= 0.98 for secrets, identifiers and media; >= 0.90 for special
categories and profilable context; false positives <= 10 %; latency and memory targets from S1; leak canary 0.

## 5. Removed (package R, once the privacy-gate service runs)

| Remove | Replaced by |
|---|---|
| `orchestrator/` (server, jobs store, Dockerfile), `ORCHESTRATOR_BEARER`, its entry in `services.py` and the tray, `.mcp.json` and `enabledMcpjsonServers`, smoke's orchestrator check | departments as LiteLLM aliases and Open WebUI models; privacy-gate (S2, S5) takes the orchestrator's place in the service list |
| `record_lesson` tool | agents append to `memory/lessons.md` directly |
| Automatic cloud tiers (`cloud.enabled: auto`, `default_fallbacks` and `context_window_fallbacks` to `cloud-*`) | private-only routers; explicit external aliases (S6) |
| Phoenix (uv tool, service entry, OTel callback, tray link) | JSONL traces, which `retro` and `why-routed` read |
| `infrastructure/docker-compose.yml` (untested) | generated `infrastructure/compose/<deployment>.yaml` |
| The tray's LiteLLM admin link while there is no database | restored once PostgreSQL is configured |
| README, AGENTS.md and `docs/ORCHESTRATOR-DESIGN.md` sections on the above | rewritten; `memory/lessons.md` keeps its history |

Kept: the native runtime (`services.py`, `startup.py`, `tray.py`, `stack.py up/down/status/tray/setup/pull`),
`agents/*.yaml` and the build, `machines/*.yaml` and `doctor`, `bench`, `smoke` (retargeted), `why-routed`, `retro`,
the trace hooks, evals.

## 6. Shared decisions (defaults used unless changed)

| # | Decision | Default |
|---|---|---|
| G1 | Regions for identifier validators, languages for lexicons | US and English; add others before go-live |
| G2 | Detector models | chosen in the S1 spike; permissive licences only |
| G3 | External models | disabled |
| G4 | `generalize` / `redact` before an intentional external send | disabled |
| G5 | Special categories allowed on confidential cloud hosts | yes (`special_categories_location: any`); set `onprem` to keep them on owned hardware |
| G6 | Users or admins may override a sensitive verdict per request | never |
