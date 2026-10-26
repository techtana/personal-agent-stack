# Shared components for Plan A (cloud-led) and Plan B (local-led)

Both plans route every model call through one LiteLLM gateway and put a privacy gate in front of every model that
is not ours. This file specifies the parts both plans build; `PLAN-A-CLOUD-LED.md` and `PLAN-B-LOCAL-LED.md` add only
what differs. Identity behaviour (TOTP, passkeys, invites with approval, roles) is specified in
`docs/GCP-DESIGN.md` section 4 and implemented here as work package S5.

Effort sizes: S = up to 1 day, M = 2-3 days, L = 4-6 days, for one developer working with the department agents.

## 0. Conventions

- **Data class on every model deployment.** `private` = hardware or VMs we run (local Ollama, the gate service, a
  private Cloud Run GPU, the on-prem server). `external` = any third-party API: Anthropic, Vertex AI, Hugging Face,
  OpenRouter, Groq and the like. Vertex AI counts as external even inside our own project. The build writes
  `model_info.data_class` on every generated deployment and fails if one is missing.
- **One policy file.** `policy/privacy.yaml` (new, hand-edited) holds detectors, thresholds, categories, actions and
  org terms. `uv run scripts/stack.py build` validates it and writes the generated gate config and LiteLLM settings.
  Host-specific values (private host URLs, models) stay in `machines/<name>.yaml` (AGENTS.md rule 2).
- **Fail closed.** If the gate errors, times out (2 s budget) or a verdict is missing, the request is treated as
  sensitive.
- **No content in logs.** Verdicts, audit rows and traces record categories and counts, never the matched text.

## 1. Policy file (`policy/privacy.yaml`)

```yaml
schema_version: 1
languages: [en]                 # detector lexicons and exemplars to load; the embedding model is multilingual
regions: [US]                   # phone and national-ID validators (decision G1)
fail_mode: closed
budget_ms: 2000
unscannable: private            # images, audio, binary attachments
detectors:
  secrets:     {enabled: true}                       # keys, tokens, private keys, connection strings
  pii:         {enabled: true}                       # email, phone, card (Luhn), IBAN, national IDs, IP (opt-in)
  ner:         {enabled: auto, combine_only: true}   # person/address names count only with another signal
  topics:      {enabled: true, threshold: 0.62}
  org_terms:   {enabled: true}
topics:                         # each has exemplar sentences in policy/topics/<name>.yaml
  health: {threshold: 0.60}
  mental_health: {threshold: 0.58}
  legal_matter: {threshold: 0.62}
  personal_finance: {threshold: 0.62}
  employment_hr: {threshold: 0.62}
  minors: {threshold: 0.55}
  security_incident: {threshold: 0.65}
org_terms:                      # literal terms and regexes that always mean sensitive
  terms: ["CONFIDENTIAL", "INTERNAL ONLY"]
  regex: []
  customers_file: policy/customers.txt   # optional, one name per line, gitignored
actions:                        # per plan; see the plan files
  on_sensitive: private
  on_private_unavailable: defer # plan A: defer | refuse ; plan B: refuse (local is the private host)
user_controls:
  force_private_models: true    # Open WebUI shows a "<Department> (private)" model per department
  override_to_external: false   # not in v1
```

## 2. Work packages

### S1. `privacy-gate` package and service (L)

Location: `packages/privacy-gate/` (own `pyproject.toml`; a uv workspace member of the repo, so tests run with
`uv run`, and installable into the LiteLLM tool environment with `--with-editable`).

Detectors, all CPU-only, loaded once:

| Detector | Method | Notes |
|---|---|---|
| secrets | regex set (cloud keys, GitHub/GitLab tokens, JWTs, PEM private keys, DB URLs with passwords, `password=`/`secret=` assignments with entropy check) | |
| pii | regex plus validators: email, phone (`phonenumbers` for configured regions), payment card (Luhn), IBAN (mod-97), national IDs per region (checksum where one exists), IP addresses (off by default: code is full of them) | |
| ner | small multilingual token-classification model in ONNX (<= 300 MB; pick in the S1 spike) | person and address entities count only together with another signal, to keep author names in code from tripping it |
| topics | multilingual sentence-embedding model in ONNX via `fastembed` (for example paraphrase-multilingual-MiniLM-L12-v2, ~220 MB); cosine similarity of 512-token chunks against exemplar sentences per topic; max over chunks | the same model also serves RAG embeddings (below) |
| org_terms | literal terms, regexes, customer list | |
| unscannable | images, audio and non-text attachments | action from `unscannable` |

Verdict (no matched text, ever):

```json
{"sensitive": true, "categories": ["pii.email", "topic.health"], "reasons": ["email address x1", "health topic"],
 "score": 0.81, "scanned_chars": 5320, "cached_parts": 4, "ms": 14, "gate_version": "1.0.0"}
```

Performance: each message part is hashed (SHA-256 of normalised text) and its verdict cached (LRU 10k entries,
24 h TTL, hashes only), so a long conversation costs only the new turn. Targets: p95 <= 50 ms for 4k tokens of new
text, <= 400 ms for 32k tokens, resident memory <= 600 MB with NER on.

Service: `gate` (Starlette + uvicorn), internal only, bearer `GATE_BEARER`.

| Endpoint | Purpose |
|---|---|
| `POST /v1/classify` | body `{messages}` or `{text}`; returns the verdict |
| `POST /v1/embeddings` | OpenAI-compatible, served by the same ONNX model; LiteLLM exposes it as `private-embed` |
| `GET /v1/private-status` | availability of each private host from a background probe (Plan A; Plan B reports local Ollama) |
| `GET /healthz` | liveness |

Acceptance: unit tests per detector; S7 targets met; service starts in under 20 s and holds the memory target.

### S2. LiteLLM enforcement hook (M)

Source: `infrastructure/litellm/privacy_hook.py` (hand-written; the config that loads it is generated). One
`CustomLogger`/`CustomGuardrail` subclass registered in `litellm_settings.callbacks`, with three layers:

1. `async_pre_call_hook` (before routing): send the full request (system prompt, all messages, tool results, `input`
   for embeddings) to `/v1/classify`; store the verdict in `data["metadata"]["privacy"]`. If sensitive:
   - rewrite `data["model"]` with the generated map: `<dept>` and `<dept>-cloud` -> `<dept>-private`;
     `cloud-*` -> `private-primary`; any embeddings -> `private-embed`;
   - set `disable_fallbacks: true`;
   - if no private host can serve it, apply `on_private_unavailable` (plan-specific). For chat call types, returning a
     string becomes a normal 200 assistant reply (LiteLLM raises `RejectedRequestError`), which is how the "queued"
     message reaches Open WebUI.
2. `async_filter_deployments` (inside routing, including fallbacks): when the verdict is sensitive or missing, drop
   every deployment whose `data_class` is not `private`; if none remain, raise.
3. `async_pre_call_deployment_hook` (just before sending): final assertion that a sensitive request is going to a
   `private` deployment, and that any `external` deployment carries a non-sensitive verdict. Otherwise raise
   `PrivacyViolation` and write an audit row. Plan A also injects the Google ID token for the private Cloud Run GPU here.

Also:
- Cover call types `completion`, `acompletion`, `anthropic_messages` (Claude Code profile B uses `/v1/messages`),
  `responses`, `embeddings`, `text_completion`.
- Disable LiteLLM pass-through routes (`/anthropic/*`, `/vertex_ai/*`, `/openai/*` and similar), which skip hooks.
  Test that they return 404.
- Write one audit row per request: request id, user, categories, action (`external`, `private`, `deferred`,
  `refused`), deployment, gate latency.

Acceptance: the leak canary in S7 passes; unit tests for the rewrite map; a request to `cloud-default` with a fake
card number is served by a private deployment.

### S3. Open WebUI integration and lock-down (M)

- **Alert filter** `config/openwebui/functions/privacy_notice.py` (source; the installer imports it as a global
  filter): in `inlet`, call `/v1/classify` on the new user message and any attached file text, and emit a
  notification through `__event_emitter__`:
  - "Sensitive content detected (personal data: email x1). It will be processed only on the private server."
  - Plan A, private host down: "The private server is offline. Your request will be queued and answered when it
    is back."
  - Plan A, private Cloud Run GPU cold: "Starting the private server; this can take a couple of minutes."
  The filter only informs; the gateway enforces.
- **Forced-private models:** the build writes a second Open WebUI model per department, "<Department> (private)",
  pointing at `<dept>-private`.
- **Lock-down settings:** one connection only (LiteLLM); `ENABLE_DIRECT_CONNECTIONS=false`; task model (titles,
  tags, follow-ups) = `webui-task`; RAG embeddings engine `openai` -> `private-embed`; web search, image generation
  and community imports off; `ENABLE_FORWARD_USER_INFO_HEADERS=true` so LiteLLM attributes spend per user
  (`general_settings.user_header_name`).

Acceptance: the notification shows for each category in a manual test; the "(private)" models exist; with web search
off, no request leaves Open WebUI except to LiteLLM (checked with a network capture during the S7 canary).

### S4. Build changes (M)

`scripts/stacklib/litellm_build.py` and `agents_build.py`:
- `cloud_models` accept provider-qualified ids (`anthropic/claude-haiku-5-5`, `vertex_ai/<model>`,
  `openai/<model>` with `api_base`); a bare id stays `anthropic/` for compatibility. Temperature stays off for
  Anthropic (AGENTS.md rule 3).
- Tag `data_class` on every deployment; generate `<dept>-private`, `private-primary`, `private-embed`, `webui-task`.
- Load `privacy_hook` and emit the guardrail settings and rewrite map from `policy/privacy.yaml`.
- Write the gate config and the Open WebUI "(private)" models.
- `stack.py gate-eval` runs S7.

Acceptance: `stack.py build` is deterministic; a deployment without `data_class` fails the build.

### S5. Identity edge (L)

Compose bundle `infrastructure/edge/` with Caddy, Authelia (OIDC provider, TOTP required, passkeys, brute-force
bans), LLDAP (users and groups, SQLite) and the invite service. Behaviour as `docs/GCP-DESIGN.md` section 4. Plan A
runs it on the main VM; Plan B runs it on a small edge VM.

- Authelia config generated from `policy/identity.yaml` (domains, session lifetimes, admin group, allowed email
  domains).
- Invite service: part of the orchestrator package (`orchestrator/invites.py`, routes under `/invite` and
  `/admin/invites`), stores requests in the orchestrator database, creates users in LLDAP over its API, sends mail
  through the configured SMTP relay.
- Open WebUI: OIDC client of Authelia, `ENABLE_LOGIN_FORM=false`, `ENABLE_SIGNUP=false`,
  `DEFAULT_USER_ROLE=pending`, groups claim mapped to Open WebUI groups.

Acceptance: the invite -> approve -> set password -> TOTP -> passkey -> pending -> active flow works end to end;
a rejected invite cannot sign in; brute force triggers a ban; admins must use a passkey.

### S6. Orchestrator for multiple users (M)

- Validate Authelia-issued tokens forwarded by Open WebUI instead of the single `ORCHESTRATOR_BEARER` (which stays
  for service-to-service calls from LiteLLM and the deferred worker).
- `user_id` on jobs, lessons and invites; every query filters on it. Plan A uses Postgres with row-level security;
  Plan B may stay on SQLite with the same filters.
- Department definitions loaded from a generated bundle, not a checkout; LiteLLM URL from configuration (already
  `LITELLM_BASE_URL`).
- Lessons are per user; an admin promotes one to shared.

Acceptance: user A cannot list, read or cancel user B's jobs (tests per tool).

### S7. Evaluation set and release gate (M)

`evals/privacy-gate/`: synthetic data only, never real personal data.
- >= 300 positives across every detector and topic, in each configured language.
- >= 300 negatives: typical coding, docs and devops prompts, including UUIDs, hashes, version numbers, sample IPs
  and author names in code.
- **Leak canary:** a mock OpenAI/Anthropic-compatible server tagged `external` records every request it receives.
  The test sends every positive through every route (department alias, explicit cloud alias, `/v1/messages`,
  embeddings, context-window overflow, a forced fallback after a 500 from the private host) and passes only if the
  mock received none of them.

Release gate (CI and `stack.py gate-eval`): recall >= 0.98 for secrets and structured PII, >= 0.90 for topics,
false positives <= 10 % on negatives, latency targets from S1, leak canary 0.

## 3. Shared decisions (defaults used unless changed)

| # | Decision | Default |
|---|---|---|
| G1 | Regions for phone and ID validators, and languages for lexicons | US and English; add others before go-live |
| G2 | NER model | chosen in the S1 spike from small multilingual ONNX models; off if it misses the memory target |
| G3 | What counts as a sensitive topic | the seven topics in section 1 |
| G4 | Users may override a sensitive verdict to use an external model | no (v1) |
| G5 | Attachments that cannot be scanned (images, audio) | treated as sensitive |
