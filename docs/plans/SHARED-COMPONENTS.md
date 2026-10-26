# Shared components for Plan A (cloud-led) and Plan B (local-led)

Revised 2026-10-26: Harbor replaces the project's own installer and service manager; the privacy gate covers
profiling risks and media (faces, people, documents in images, video, audio); the orchestrator is removed and its MCP
slot goes to a privacy-gate MCP server plus a skill. Dependencies and configuration steps: `INSTALL.md`.

Both plans route every model call through one LiteLLM gateway and put a local privacy gate in front of every model that
is not ours. This file specifies the parts both plans build; the plan files add only what differs. Identity
behaviour (TOTP, passkeys, invites with approval, roles) is in `docs/GCP-DESIGN.md` section 4.

Effort sizes: S = up to 1 day, M = 2-3 days, L = 4-6 days, for one developer working with the department agents.

## 0. Conventions

- **Runtime: Harbor.** Harbor (open-source CLI, Docker Compose underneath) installs and runs the off-the-shelf services:
  Open WebUI and LiteLLM, plus Ollama where it runs in a container. Our own services (privacy gate, identity edge) are
  one small Compose project attached to Harbor's Docker network. Ollama on Windows stays native (GPU, mmap tuning in
  `memory/state.md`) and Harbor points at it with `ollama.internal_url`.
- **This repo keeps only what Harbor does not do:** department definitions and their generated files, hardware-based
  model choice, the privacy gate, policy, evals, retro. See section 3 for what is removed.
- **Data class on every model deployment.** `private` = hardware or VMs we run (local Ollama, the gate, a private
  Cloud Run GPU, the on-prem server). `external` = any third-party API, Vertex AI included. The build writes
  `model_info.data_class` on every deployment and fails if one is missing.
- **One policy file**, `policy/privacy.yaml`, hand-edited and validated by `stack.py build`.
- **Fail closed.** A gate error, a timeout or a missing verdict counts as sensitive.
- **No content in logs.** Verdicts, audit rows and traces record categories and counts only.
- **All detection runs locally** (on our machine or our VM), on CPU, before anything leaves.

## 1. What the gate protects against

Two risks, not one: a single request exposing something sensitive, and many harmless-looking requests letting a
provider build a profile of a person.

| Group | Categories |
|---|---|
| Direct identifiers | names with context, email, phone, postal address, government and account numbers, payment cards, IBAN, usernames and handles, device IDs, IP and MAC addresses (opt-in), licence plates |
| Quasi-identifiers | age or birth date, small-area location, employer and job title, school, nationality. Two or more about the same person count as sensitive |
| Special categories | health and mental health; sex life, sexual orientation and gender identity; racial or ethnic origin; religious or philosophical beliefs; political opinions; trade-union membership; genetic and biometric data; criminal records |
| Profilable personal context | personal interests and lifestyle (hobbies, routines, habits, memberships); family and relationships; precise location and movement patterns (home, schedules, travel plans); personal finances; employment and HR matters; children and minors; private messages from or about other people |
| Secrets and confidential | keys, tokens, passwords, connection strings; organisation terms and customer lists |
| Media | faces, people or bodies, nudity, identity documents and screens with personal text, location metadata (EXIF GPS), voices |

**Personal-disclosure rule.** Topic categories count only when they are about a person: first-person statements
("I", "my") or text about an identified or identifiable person. "How do I true a bicycle wheel" is not sensitive;
"I ride every Saturday at 6 from the park next to my flat" is (routine plus location). This keeps false positives on
ordinary technical work low.

**Anti-profiling measures for what does go external** (requests the gate passes):
- One shared provider key for all users; LiteLLM never forwards user ids, emails, Open WebUI user headers or the
  `user` field to a provider.
- Open WebUI personalisation stays local. A request whose system prompt carries user variables (name, location,
  date of birth) or saved memories is classified like any other text, so personal memories keep it local. Admins can
  turn memories off for external models instead.
- Provider options that limit retention and training are switched on where the provider offers them (checked per
  provider at install).
- Optional `generalize` action per category (off by default): the local model rewrites the request without the
  personal details, the user sees the rewritten text, and only that goes external.

## 2. Work packages

### S1. `privacy-gate`: detectors (L)

Location: `packages/privacy-gate/` (own `pyproject.toml`, uv workspace member; ships as a container image too).

Text detectors (CPU):

| Detector | Method |
|---|---|
| secrets | regex set plus entropy checks |
| identifiers | regex plus validators (`phonenumbers` per configured region, Luhn, IBAN mod-97, national-ID checksums) |
| ner | small multilingual ONNX token-classification model; persons, places, organisations feed the quasi-identifier and disclosure rules |
| disclosure | first-person and identified-person cues (lexicon plus the NER output) |
| topics | multilingual ONNX sentence-embedding model via `fastembed` against exemplar sentences per category in `policy/topics/*.yaml`; max over 512-token chunks |
| quasi-identifier combiner | two or more quasi-identifiers linked to one person -> sensitive |
| org_terms | literal terms, regexes, customer list |

Media detectors (S1b, M), all ONNX on CPU, models chosen in the S1 spike with permissive licences (record each
licence in `packages/privacy-gate/MODELS.md`):

| Input | Pipeline |
|---|---|
| image | read EXIF (GPS, device, owner fields) -> face detector (OpenCV YuNet class) -> person detector -> nudity classifier -> OCR (RapidOCR class) whose text goes through the text detectors |
| video | `ffmpeg` samples 1 frame per second plus scene changes (capped at 120 frames) -> image pipeline; the audio track counts as voice |
| audio | voice is biometric: sensitive by default; optional local transcription (whisper.cpp class) to scan the words as text |
| documents (PDF, Office) | extracted text -> text detectors; embedded images -> image pipeline |
| anything else binary | `unscannable` -> treated as sensitive |

Verdict (never contains matched text):

```json
{"sensitive": true, "categories": ["special.health", "media.face"], "reasons": ["health topic, first person", "1 face"],
 "score": 0.84, "scanned": {"chars": 5320, "images": 1, "frames": 0}, "cached_parts": 4, "ms": 61, "gate_version": "1.0.0"}
```

Performance targets: text p95 <= 50 ms for 4k new tokens and <= 400 ms for 32k; image p95 <= 300 ms; video <= 20 s
per minute of footage; resident memory <= 900 MB with every detector loaded. Parts are cached by SHA-256 (hashes
only, LRU 10k, 24 h).

### S1c. Redaction (M)

`redact` produces a copy that is safe to send when the policy allows it: masks text spans; blurs faces, people and
OCR regions with personal text; strips all metadata. The result is scanned again and only passes if clean. Used by
the optional `redact_then_external` media action and offered as an MCP tool. Default policy keeps media with people
local.

### S2. Gate service (M)

One service, `privacy-gate`, internal only, bearer `GATE_BEARER`:

| Endpoint | Purpose |
|---|---|
| `POST /v1/classify` | messages, text or file references -> verdict |
| `POST /v1/redact`, `POST /v1/generalize` | S1c; `generalize` calls the private chat model through LiteLLM |
| `POST /v1/embeddings` | OpenAI-compatible, same ONNX model; exposed in LiteLLM as `private-embed` for Open WebUI's RAG |
| `GET /v1/private-status` | availability of each private host (Plan A); local Ollama (Plan B) |
| `/mcp` | the MCP server (S5) |
| `GET /healthz` | liveness |

Plan A adds the deferred queue to this service (it already knows when private hosts are up).

### S3. LiteLLM enforcement hook (M)

`infrastructure/litellm/privacy_hook.py`, mounted into Harbor's LiteLLM container with the generated config.
Three layers:

1. `async_pre_call_hook`: classify the full request (system prompt, messages, tool results, image and file parts,
   embeddings `input`). If sensitive: rewrite `<dept>`, `<dept>-cloud` and `cloud-*` to the private alias, embeddings
   to `private-embed`, set `disable_fallbacks: true`, and apply `on_private_unavailable` when no private host can
   serve it. A returned string becomes a normal assistant reply (LiteLLM `RejectedRequestError`). Strip user
   identifiers before any external call (section 1).
2. `async_filter_deployments`: for a sensitive or unclassified request, drop every non-`private` deployment, so
   fallbacks cannot reach an external one.
3. `async_pre_call_deployment_hook`: final assertion before sending; raise `PrivacyViolation` and audit on any
   mismatch.

Cover `completion`, `anthropic_messages` (`/v1/messages`), `responses`, `embeddings`, `text_completion`,
`image_generation` (prompts) and audio transcription. Disable pass-through routes (`/anthropic/*`, `/vertex_ai/*` and
similar), which skip hooks. One audit row per request (user, categories, action, deployment, latency).

### S4. Open WebUI integration (M)

- **Filter function** `config/openwebui/functions/privacy_notice.py`: on each new message and upload, call
  `/v1/classify` and show a notification naming the categories and what will happen ("kept on the private server",
  "queued", "starting the private server", "image contains 2 faces: processed locally"). It informs; LiteLLM
  enforces.
- **Forced-private models**: "<Department> (private)" per department.
- **Settings** (applied by the installer through Harbor's `harbor env webui ...` and the Open WebUI API):
  one connection (LiteLLM); direct connections off; task model `webui-task`; RAG embeddings `private-embed`; web search
  and image generation off unless routed through the gate; community imports off; user-info headers on for LiteLLM
  attribution (never forwarded to providers); the privacy-gate MCP server registered as a tool server (S5).

### S5. MCP server and skill (M)

For apps where we cannot sit in the model path, or where an agent should check before it acts.

**MCP server** (`/mcp` on the gate service; also `privacy-gate mcp --stdio` for desktop clients):

| Tool | Does |
|---|---|
| `check_text`, `check_file`, `check_media` | return the verdict and plain-language reasons |
| `redact` | returns the redacted text or media and what was removed |
| `generalize` | returns a generic rewrite made by the private model |
| `policy` | lists the categories and actions in force |

Clients and how they connect (generated where the app reads a config file):

| App | Connection |
|---|---|
| Open WebUI | tool server, MCP Streamable HTTP, registered by the installer |
| Claude Code | `.mcp.json` entry `privacy-gate` (replaces `orchestrator`) |
| Claude Desktop, other stdio-only clients | `privacy-gate mcp --stdio` in the app's MCP config |
| OpenCode, Continue, Cursor, Zed and other MCP clients | HTTP or stdio, same tools |

**Skill** `skills/privacy-check/SKILL.md` (Agent Skills format; the build copies it to `.claude/skills/` and
`.opencode/skills/`): before sending pasted data, files, screenshots or web queries to any external tool or model,
call `check_*`; if sensitive, keep the work local, offer `redact` or `generalize`, and never paste the raw content
into an external call.

**Claude Code hooks** (generated into `.claude/settings.json`): `UserPromptSubmit` warns or blocks on a sensitive
prompt; `PreToolUse` on `WebSearch`, `WebFetch` and external MCP tools checks the outgoing arguments.

Limits, stated in the user guide: MCP tools, skills and hooks are advisory. They cannot see everything an app sends
to its own cloud model. Only apps pointed at the LiteLLM gateway get enforcement.

### S6. Build changes (M)

`scripts/stacklib/litellm_build.py`, `agents_build.py`:
- provider-qualified `cloud_models` (`anthropic/...`, `vertex_ai/...`, `openai/...` with `api_base`); no temperature
  for Anthropic (AGENTS.md rule 3);
- `data_class` on every deployment; generate `<dept>-private`, `private-embed`, `webui-task`, vision-capable
  private deployment for media;
- load `privacy_hook`; write the gate config, the "(private)" Open WebUI models, the skill copies, the `.mcp.json`
  entry and the Claude Code hooks;
- write the LiteLLM config where Harbor's LiteLLM service reads it (path confirmed in the H0 spike, `INSTALL.md`).

### S7. Identity edge (L)

Unchanged from the previous revision: Caddy, Authelia (OIDC, TOTP required, passkeys, bans), LLDAP, and a small
invite service (`packages/identity-edge/invites`, its own SQLite) as a Compose project in `infrastructure/edge/`.
Behaviour per `docs/GCP-DESIGN.md` section 4. Open WebUI uses Authelia as its OIDC provider, with signup and the login
form off and `DEFAULT_USER_ROLE=pending`.

### S8. Evaluation and release gate (M)

`evals/privacy-gate/`, synthetic data only:
- >= 40 positives per category in section 1 (in each configured language), including profiling cases (single
  quasi-identifiers that must pass, combinations that must not; interest topics with and without personal
  disclosure);
- >= 300 negatives from ordinary coding, docs and devops work;
- media set: generated or licensed images and clips with and without faces, people, documents, GPS metadata; no
  photos of real people without their consent;
- **leak canary**: a mock external provider records everything it receives; every positive goes through every route
  (department alias, explicit cloud alias, `/v1/messages`, embeddings, image parts, context overflow, forced fallback)
  and the mock must receive none.

Release gate (`stack.py gate-eval`, CI): recall >= 0.98 for secrets, identifiers and media; >= 0.90 for special
categories and profilable context; false positives <= 10 % on negatives; latency and memory targets from S1; leak
canary 0.

## 3. Removed (package R, after Harbor runs the stack on SEKAIHOME and smoke passes)

| Remove | Replaced by |
|---|---|
| `orchestrator/` (server, jobs store, Dockerfile), `ORCHESTRATOR_BEARER`, the `orchestrator` entry in `.mcp.json`, smoke's MCP check | departments as LiteLLM aliases, Open WebUI models and Claude Code subagents; MCP slot -> privacy-gate (S5) |
| `record_lesson` tool | agents append to `memory/lessons.md` directly (AGENTS.md rule 6 updated) |
| `scripts/stacklib/services.py`, `scripts/stacklib/startup.py`, `scripts/tray.py`; `stack.py up`, `down`, `status`, `tray`, `setup`, `pull` | `harbor up`, `down`, `ps`, `logs`; Docker restart policies for start at boot; `ollama pull` / `harbor` for models; `stack.py install` (thin wrapper, `INSTALL.md`) |
| uv tool installs of litellm, open-webui and arize-phoenix; the Smart App Control launcher workaround | Harbor containers |
| Phoenix (and its OTel callback) | JSONL traces, which `retro` and `why-routed` already read; Harbor's Langfuse if a tracing UI is wanted later |
| `infrastructure/docker-compose.yml` | Harbor's compose plus `infrastructure/gate/` and `infrastructure/edge/` |
| README, AGENTS.md and `docs/ORCHESTRATOR-DESIGN.md` sections on the above | rewritten; `memory/lessons.md` keeps its history |

Kept: `agents/*.yaml` and the build, `machines/*.yaml` and `doctor` (model choice per machine), `bench`, `smoke`
(retargeted), `why-routed`, `retro`, the Claude Code hooks, evals.

## 4. Shared decisions (defaults used unless changed)

| # | Decision | Default |
|---|---|---|
| G1 | Regions for identifier validators, languages for lexicons | US and English; add others before go-live |
| G2 | Detector models (NER, faces, people, nudity, OCR) | chosen in the S1 spike; permissive licences only |
| G3 | `generalize` action | off; can be enabled per category |
| G4 | Media with people or documents | processed locally; `redact_then_external` available but off |
| G5 | Voice audio | sensitive; local transcription optional |
| G6 | Users may override a verdict to use an external model | no |
