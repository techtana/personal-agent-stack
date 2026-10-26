# Plan A: cloud-led mixture

Revised 2026-10-26: Harbor runtime, broader privacy gate (profiling, media), orchestrator removed.

A small cloud VM is the main processor and model work goes to pay-per-token APIs. A local privacy gate on the VM checks
every request, including images, video and audio. Requests with personal or profilable information, secrets or media
showing people alert the user and go only to a private server: a private Cloud Run GPU, the on-prem machine, or both
in priority order. They never go to Vertex AI, Hugging Face or any other external API. If no private server is
available, the request is queued and answered when one comes back.

Prerequisites: `SHARED-COMPONENTS.md` (S1-S8, R), `INSTALL.md` (section 2.2). Identity and security posture follow
`docs/GCP-DESIGN.md` (one-VM revision) except where this plan differs.

## 1. Topology

```
Browser ─HTTPS─▶ Caddy ─┬─ auth.<domain>  Authelia + LLDAP + invites                      (S7)
  (Google Cloud VM,     └─ chat.<domain>  Open WebUI [Harbor] + privacy_notice filter       (S4)
   e2-medium, Docker)                       │ tools: privacy-gate MCP (S5)
                                            ▼
                               LiteLLM [Harbor] + privacy_hook (S3) ──▶ privacy-gate (S1-S2):
                                │ not sensitive                         classify, redact, embeddings,
                                ▼                                       private status, deferred queue
                    external APIs by complexity tier        │ sensitive
                    (identifiers stripped)                  ▼
                                                 private hosts, in priority order
                                                 ├─ onprem: Ollama on SEKAIHOME over WireGuard (VM is the hub)
                                                 └─ gcp-gpu: Cloud Run + L4, min 0, max 1, internal + IAM
                                                        │ none available
                                                        ▼
                                                 deferred queue (privacy-gate + Postgres, encrypted)

Also on the VM: Postgres, WireGuard hub. Nightly backups to Cloud Storage.
```

| Component | Where | Data class |
|---|---|---|
| Open WebUI, LiteLLM (Harbor); privacy-gate, Postgres, identity edge (our Compose) | VM in our project (trusted, encrypted disk) | private |
| RAG embeddings, all detection and redaction | privacy-gate on the VM | private |
| Non-sensitive chat | external APIs, with user identifiers stripped | external |
| Sensitive chat and media | private hosts only (a vision-capable private model for images and video) | private |

## 2. Routing rules

| Request | Gate verdict | Private host | Action |
|---|---|---|---|
| chat | not sensitive | - | `<dept>` complexity router: cheap / default / heavy API model |
| chat or media | sensitive | available | `<dept>-private` (vision deployment for media), fallbacks off, alert names the categories |
| chat or media | sensitive | none | enqueue; reply at once: "Queued as Q-1234: this needs the private server, which is offline..." |
| `webui-task` (titles, tags) | sensitive | none | fixed title "Private chat"; not queued |
| embeddings | any | - | `private-embed` on the VM |
| media, policy `redact_then_external` enabled | sensitive only because of media | - | redact (S1c), re-scan, then external if clean; user notified |
| category with `generalize` enabled | sensitive | - | local rewrite shown to the user, then external |
| gate error, unscannable file | - | - | treated as sensitive |
| "<Department> (private)" model | - | - | private path, whatever the verdict |
| sensitive, longer than the private model's context | - | - | reply asking to shorten or split; never external |

### 2.1 Private hosts

```yaml
# machines/<vm-hostname>.yaml (class cloud-first: no local models on the VM)
deployment: cloud-led
private_hosts:                           # highest priority first; remove one for "on-prem only" or "cloud GPU only"
  - {name: onprem,  kind: ollama, url: http://10.66.0.2:11434, model: qwen3.5:9b, vision_model: <local vision model>, num_ctx: 32768}
  - {name: gcp-gpu, kind: ollama, url: https://private-gpu-<hash>-<region>.run.app, auth: google-id-token,
     model: qwen3.5:9b, vision_model: <local vision model>, num_ctx: 32768, cold_start_timeout_s: 300}
cloud_models:
  cheap:   anthropic/claude-haiku-5-5
  default: anthropic/claude-sonnet-5-5
  heavy:   anthropic/claude-opus-5-5
```

Availability (privacy-gate background probe): `onprem` is up after two consecutive successful `GET /api/tags` with
the model present (every 15 s) and down after two failures. `gcp-gpu` is available unless in a 10-minute backoff
after a failed start; a cold start is waited out up to `cold_start_timeout_s` while the filter shows "starting".
Both hosts form one `<dept>-private` model group with `order`, so failover stays inside the private class.

### 2.2 Deferred queue (in privacy-gate)

Table `deferred_requests` in Postgres: `id` (`Q-…`), `user_id`, `chat_id` (when Open WebUI forwards it), `model`,
`request_enc` and `result_enc` (AES-256-GCM, key `DEFERRED_KEY` from Secret Manager, nonce per row; media stored
encrypted alongside), `status` (`queued`, `running`, `done`, `failed`, `expired`, `cancelled`), `attempts`,
timestamps, `error`.

1. The hook calls `POST /internal/deferred` and returns the "queued" text as the assistant reply.
2. A worker in privacy-gate replays FIFO per user when a private host is up, one at a time, with header
   `x-privacy-replay: <id>`; the hook allows replays only to private deployments.
3. Delivery: an email without content; MCP tools `list_deferred`, `get_deferred`, `cancel_deferred` on the
   privacy-gate MCP server, available in Open WebUI; stretch goal: append the answer to the original chat through the
   Open WebUI API.
4. Limits: 20 queued per user, 500 total, 25 MB per request; expiry 72 h; results deleted 7 days after delivery;
   audit row per step.

## 3. Work packages

| # | Package | Size | Depends on |
|---|---|---|---|
| A0 | Decisions and accounts (section 6) | S | - |
| H0 | Harbor spike on a Linux VM: install, config keys, network, mounting our LiteLLM config and hook | S | - |
| S1-S6, S8 | shared gate, hook, Open WebUI, MCP and skill, build, evals | see shared file | H0 |
| A1 | Build target `deployment: cloud-led`: private host groups with `order`, vision deployments, `cloud-first` VM profile, `infrastructure/gate/compose.yaml` with the deferred worker and Postgres | M | S6 |
| A2 | Terraform `infrastructure/gcp/`: APIs, VM with startup script (Docker, Harbor, uv, WireGuard per `INSTALL.md` 2.2), static IP, firewall (443/tcp, 51820/udp), service accounts, Secret Manager, backup bucket, billing budget alert | M | A0, H0 |
| A3 | On-prem private host: WireGuard hub; `stack.py wg-config` for SEKAIHOME; Ollama on the tunnel address only; firewall rule | M | A2 |
| A4 | Cloud GPU private host: Cloud Run Ollama image with text and vision models baked in, L4, min 0, max 1, internal ingress, IAM; ID-token injection in S3 layer 3 | M | A2 |
| A5 | Deferred queue in privacy-gate (section 2.2) | L | S2, S3 |
| S7 | Identity edge on the VM | L | A2 |
| A6 | Cloud Shell installer `scripts/gcp-install.sh` with `destroy` and `restore <date>` | M | A1-A5, S7 |
| A7 | Tests on a staging project (section 4) | M | all |
| R | Remove redundant parts (shared file section 3) | S | A7 |
| A8 | User guide and admin runbook | S | A7 |

Order: A0, H0 -> S1, S1b, S8 (prove detection first) -> S2, S3, S6, A1 -> S4, S5 -> A5 -> A2 -> A3 or A4 -> S7 ->
A6 -> A7 -> R -> A8.

Out of scope: agents that clone and change repositories on the server; OpenHands; high availability.

## 4. Acceptance tests

1. Leak canary (S8) on the deployed stack: 0 sensitive requests or media reach the external mock on any route.
2. External requests carry no user id, email, name or forwarded headers (checked at the mock).
3. Sensitive chat with `onprem` up: answered on-prem; notification names the categories; audit `private/onprem`.
4. A photo with a face: processed by the private vision model; never reaches the mock.
5. `onprem` down: `gcp-gpu` answers after a cold start with the "starting" notice.
6. Every private host down: "queued" reply within 3 s; answer delivered within 2 minutes of a host returning, with an
   email and `get_deferred`; database rows not readable as plain text; expiry after 72 h with notice.
7. Non-sensitive chat goes external; gate overhead p95 <= 100 ms for text on the VM.
8. Cross-user: user B cannot see or cancel user A's deferred requests.
9. Restore drill under 1 hour; install from an empty project under 45 minutes (excluding DNS and quota waits).

## 5. Cost (rough, unverified)

| Item | Month |
|---|---|
| e2-medium VM, disk, static IP, backups | ~$30 |
| `onprem` private host | $0 |
| `gcp-gpu` private host | ~$1 per hour while running, $0 idle |
| External APIs | per token |
| **Idle floor** | **~$30** |

## 6. Decisions

| # | Decision | Default |
|---|---|---|
| A-D1 | Private hosts and order | `onprem`, then `gcp-gpu` |
| A-D2 | External provider per tier | Anthropic Haiku / Sonnet / Opus 5.5 |
| A-D3 | Domain and DNS provider | required |
| A-D4 | Region (Cloud Run L4 availability) | us-central1 |
| A-D5 | Queue limits and expiry | 20 per user, 72 h, results kept 7 days |
| A-D6 | The cloud VM may store sensitive chats at rest (our project, encrypted disk) | yes; if not, choose Plan B |
| A-D7 | SMTP relay | required |
| A-D8 | Local vision model for media | chosen in S1 spike; must fit the private hosts' VRAM |

## 7. Risks

| Risk | Mitigation |
|---|---|
| Gate misses something | layered detectors; fail closed; S8 recall gate; forced-private models; weekly audit review in the retro |
| Too many false positives fill the queue | personal-disclosure rule; per-category thresholds tuned on S8; categories shown in alerts so users can report mistakes |
| Profiling through many small non-sensitive requests | identifiers stripped; one shared key; memories keep requests local; optional `generalize` |
| On-prem offline for days | `gcp-gpu` second; expiry notices |
| Harbor changes how a service is configured | Harbor and service images pinned; H0 notes in `INSTALL.md`; S8 canary runs before any upgrade |
