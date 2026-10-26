# Plan A: cloud-led mixture

A small cloud VM is the main processor and model work goes to pay-per-token APIs. A lightweight privacy gate checks
every request. Requests with personal data, secrets or sensitive topics alert the user and go only to a private
server: a private Cloud Run GPU, the on-prem machine, or both in priority order. They never go to Vertex AI,
Hugging Face or any other external API. If no private server is available, the request is queued and answered when one
comes back.

Prerequisite reading: `SHARED-COMPONENTS.md` (S1-S7). Infrastructure, identity and security posture follow
`docs/GCP-DESIGN.md` (one-VM revision) except where this plan says otherwise.

## 1. Topology

```
Browser ─HTTPS─▶ Caddy ─┬─ auth.<domain>  Authelia + LLDAP + invite service          (S5)
  (Google Cloud VM,     └─ chat.<domain>  Open WebUI + privacy_notice filter          (S3)
   e2-medium)                               │
                                            ▼
                                LiteLLM + privacy_hook (S2) ──▶ gate service (S1): classify, embeddings, private status
                                 │ not sensitive                   │ sensitive
                                 ▼                                 ▼
                     external APIs by complexity tier     private hosts, in priority order
                     (Anthropic / Vertex / OpenAI-        ├─ onprem: Ollama on SEKAIHOME over WireGuard (VM is the hub)
                      compatible; data_class external)    └─ gcp-gpu: Cloud Run + L4, min 0, max 1, internal + IAM
                                                                   │ none available
                                                                   ▼
                                                      deferred queue (orchestrator, Postgres, encrypted)
                                                      ─▶ answered when a private host returns; user notified

Also on the VM: orchestrator MCP (S6) + deferred worker, Postgres, WireGuard hub. Nightly backups to Cloud Storage.
```

What runs where:

| Component | Where | Data class |
|---|---|---|
| Open WebUI, LiteLLM, gate, orchestrator, Postgres, identity edge | VM in our project (trusted, encrypted disk) | private |
| RAG embeddings | gate service on the VM (`private-embed`) | private |
| Non-sensitive chat and jobs | external APIs | external |
| Sensitive chat and jobs | private hosts only | private |

## 2. Routing rules

| Request | Gate verdict | Private host | Action |
|---|---|---|---|
| any chat or job | not sensitive | - | `<dept>` complexity router: simple/medium -> cheap API model, complex -> default, reasoning -> heavy |
| any chat or job | sensitive | available | `<dept>-private` for every tier, fallbacks off, alert "private" (and "quality may be lower" for complex tiers) |
| Open WebUI chat | sensitive | none | enqueue, reply at once: "Queued as Q-1234 because the private server is offline..." |
| orchestrator job | sensitive | none | HTTP 503 `private_unavailable`; job status `waiting_private`; the orchestrator retries it (no second queue) |
| `webui-task` (titles, tags) | sensitive | none | return the fixed title "Private chat"; never queued |
| embeddings | any | - | `private-embed` on the VM |
| gate error or timeout | - | - | treated as sensitive |
| image, audio, binary | - | - | treated as sensitive (G5) |
| "<Department> (private)" model | - | - | private path, whatever the verdict |
| sensitive, longer than the private model's context | - | - | reply asking to shorten or split; never external |

### 2.1 Private hosts

Configured in the VM's machine file, highest priority first:

```yaml
# machines/<vm-hostname>.yaml (class cloud-first: no local models on the VM)
deployment: cloud-led
private_hosts:
  - name: onprem
    kind: ollama
    url: http://10.66.0.2:11434          # SEKAIHOME over WireGuard
    model: qwen3.5:9b
    num_ctx: 32768
  - name: gcp-gpu
    kind: ollama
    url: https://private-gpu-<hash>-<region>.run.app
    auth: google-id-token
    model: qwen3.5:9b
    num_ctx: 32768
    cold_start_timeout_s: 300
cloud_models:                             # external, per complexity tier
  cheap:   anthropic/claude-haiku-5-5
  default: anthropic/claude-sonnet-5-5
  heavy:   anthropic/claude-opus-5-5
```

Either host can be removed to get "cloud GPU only" or "on-prem only".

Availability, from the gate's background probe:
- `onprem`: `GET /api/tags` every 15 s over WireGuard. It is available after two consecutive successes with the
  model present, and unavailable after two failures.
- `gcp-gpu`: available unless it is in failure backoff. With min 0 the first request cold-starts the service; the
  hook waits up to `cold_start_timeout_s` and the filter shows "starting". A failed start (quota, 5xx, timeout) puts
  the host in a 10-minute backoff, during which it counts as unavailable.

LiteLLM puts both hosts in one `<dept>-private` model group (priority order through `order`), so a failure on
`onprem` moves to `gcp-gpu` within the private class. Fallbacks never cross into `external` (S2 layer 2).

### 2.2 Deferred queue

Owned by the orchestrator, because it already runs background jobs and has a database.

Table `deferred_requests` (Postgres, row-level security on `user_id`):

| Column | Notes |
|---|---|
| `id` | `Q-` + short id shown to the user |
| `user_id`, `chat_id` | from Open WebUI's forwarded user headers (`chat_id` when Open WebUI sends it) |
| `model` | the `<dept>-private` alias to replay |
| `request_enc`, `result_enc` | AES-256-GCM; key `DEFERRED_KEY` from Secret Manager; a random nonce per row |
| `status` | `queued`, `running`, `done`, `failed`, `expired`, `cancelled` |
| `attempts`, `created_at`, `expires_at`, `done_at`, `notified_at`, `error` | |

Flow:
1. The hook calls `POST /internal/deferred` on the orchestrator (service bearer) with the request and verdict
   categories, then returns the "queued" text as the assistant reply.
2. A worker in the orchestrator checks `/v1/private-status` every 30 s. When a host is available it replays requests
   FIFO per user, one at a time by default, calling LiteLLM with the `<dept>-private` alias and the header
   `x-privacy-replay: <id>` (the hook allows a replay only to private deployments and never re-queues it).
3. On success: encrypt and store the result, then notify the user:
   - email without content ("Your private request Q-1234 is ready"), through the S5 SMTP relay;
   - Open WebUI tools `list_deferred`, `get_deferred` and `cancel_deferred` (orchestrator MCP), enabled on every
     department model, so the user can ask "show my queued requests";
   - stretch goal A6b: append the answer to the original chat through the Open WebUI API.
4. Limits: 20 queued per user, 500 in total, 1 MB per request. Queued requests expire after 72 h and results are
   deleted 7 days after delivery; the user is told in both cases. Every step writes an audit row.

## 3. Work packages

Shared packages S1-S7 come first (see `SHARED-COMPONENTS.md`). Plan-specific packages:

| # | Package | Size | Depends on |
|---|---|---|---|
| A0 | Decisions and accounts (section 6): domain, GCP project with billing budget, API keys, SMTP relay | S | - |
| A1 | Build target `deployment: cloud-led`: private host groups with `order`, `cloud-first` class on the VM, generated `infrastructure/compose/cloud-led.yaml` | M | S4 |
| A2 | Images: LiteLLM + `privacy_hook` + `privacy-gate` (pinned), gate service, orchestrator (existing `orchestrator/Dockerfile`), upstream Open WebUI / Authelia / LLDAP / Caddy / Postgres pinned by digest | M | S1, S2, S6 |
| A3 | Terraform `infrastructure/gcp/`: APIs, VM (Debian + Docker, startup script), static IP, firewall (443/tcp, 51820/udp), service accounts, Secret Manager, backup bucket (versioned, 30-day lifecycle), billing budget alert | M | A0 |
| A4 | On-prem private host: WireGuard hub on the VM; `stack.py wg-config` writes the Windows client config for SEKAIHOME; Ollama listens on the WireGuard address; Windows Firewall allows 11434 only from the VM's tunnel address | M | A3 |
| A5 | Cloud GPU private host: Cloud Run service with Ollama and the model baked into the image, L4, min 0, max 1, internal ingress, IAM invoker for the VM's service account; ID-token injection in S2 layer 3; GPU quota request documented | M | A3 |
| A6 | Deferred queue: table, encryption, `/internal/deferred`, worker, MCP tools, email notice, expiry; hook integration | L | S2, S6 |
| A7 | Installer `scripts/gcp-install.sh` for Cloud Shell, with `destroy` and `restore <date>` | M | A1-A5 |
| A8 | Tests on a staging project (section 4) | M | all |
| A9 | User guide (what the alerts mean, how queued requests work, forced-private models) and admin runbook | S | A8 |

Suggested order: A0 -> S1, S7 (the gate is the riskiest part; prove recall and latency first) -> S2, S4, A1 -> S3,
S6 -> A6 -> A2, A3 -> A4 or A5 -> S5 -> A7 -> A8 -> A9.

Out of scope for this plan: orchestrator coding jobs that clone repositories into sandboxes (the orchestrator today
only sends chat-completion jobs to LiteLLM); OpenHands; high availability.

## 4. Acceptance tests

1. Leak canary (S7) on the deployed stack: 0 sensitive requests reach the external mock across every route.
2. Sensitive chat with `onprem` up: answered by the on-prem model; the notification shows; the audit row says
   `private/onprem`.
3. `onprem` down, `gcp-gpu` configured: answered by `gcp-gpu` after a cold start; the "starting" notice shows.
4. Every private host down: the "queued" reply arrives within 3 s. Bringing `onprem` back delivers the answer within
   2 minutes, with an email and the result shown by `get_deferred`. The database row is not readable as plain text.
5. Expiry: a queued request older than 72 h is deleted and the user is notified.
6. Non-sensitive chat goes to the external tier the complexity router picks; gate overhead p95 <= 100 ms on the VM.
7. Cross-user: user B cannot list, read or cancel user A's deferred requests or jobs.
8. Restore drill: rebuild the VM from Terraform and last night's backup in under 1 hour.
9. Install from an empty project with one script in under 45 minutes, excluding DNS and quota waits.

## 5. Cost (rough, unverified; check in the pricing calculator)

| Item | Month |
|---|---|
| e2-medium VM, disk, static IP, backups | ~$30 |
| Private host `onprem` | $0 (owner's electricity) |
| Private host `gcp-gpu` | ~$1 per hour while running, $0 idle (min 0) |
| External APIs | per token; Haiku 5.5 at $0.10/$0.50 per MTok makes routine work cheap |
| **Idle floor** | **~$30** |

## 6. Decisions needed before A0

| # | Decision | Default if not decided |
|---|---|---|
| A-D1 | Private hosts and their order | `onprem`, then `gcp-gpu` |
| A-D2 | External API provider per tier | Anthropic Haiku / Sonnet / Opus 5.5 |
| A-D3 | Domain and DNS provider | none; required |
| A-D4 | Region (needs Cloud Run L4 availability if `gcp-gpu` is used) | us-central1 |
| A-D5 | Queue limits and expiry | 20 per user, 72 h, results kept 7 days |
| A-D6 | Is the cloud VM trusted to store sensitive chats at rest? This plan assumes yes (our project, encrypted disk). If not, Plan B fits better. | yes |
| A-D7 | SMTP relay for invites and notices | none; required |

## 7. Risks

| Risk | Mitigation |
|---|---|
| The gate misses something (false negative) | layered detectors; fail closed; S7 recall gate before go-live; forced-private models for users who know a chat is sensitive; audit review in the weekly retro |
| Too many false positives slow people down or fill the queue | per-topic thresholds tuned on S7; categories shown in the alert so users can report mistakes; admins adjust `policy/privacy.yaml` |
| On-prem machine offline for days | `gcp-gpu` as the second host; queue expiry with notice |
| Cold starts on `gcp-gpu` feel slow | model baked into the image; "starting" notice; optional min 1 during working hours (costs per hour) |
| A new LiteLLM release changes hook behaviour | LiteLLM pinned; the S7 leak canary runs in CI before any version bump |
