# Multi-user deployment on Google Cloud (draft, superseded 2026-10-26)

Superseded by `docs/plans/` (private first). Kept for its reasoning only. Its defaults contradict the current
direction: Vertex AI and other APIs as default model hosts, a non-confidential VM and Cloud Run GPU, Google Secret
Manager, and the orchestrator. The identity design (section 4) moved to `docs/plans/SHARED-COMPONENTS.md` S7.

Status: proposal, nothing built. Implementation plans that build on it: `docs/plans/` (Plan A cloud-led, Plan B
local-led); where they differ (Vertex AI counts as external there, and the privacy gate decides routing), the plans win. It extends the single-developer stack in `docs/ORCHESTRATOR-DESIGN.md` to a shared,
multi-user deployment used only through open-source front ends. The local stack (`machines/<HOST>.yaml`, tray,
Claude Code surfaces) stays as it is; the shared deployment is a second target generated from the same
`agents/*.yaml`.

Revision note: the first draft (managed Cloud Run services with minimum instances, Cloud SQL, an HTTPS load balancer
with Cloud Armor, Authentik, Phoenix and an in-project GPU) had an idle floor of roughly $100-200 a month before any
model use. This revision targets roughly $15-35 a month idle by putting the whole control plane on one small VM and
paying for models only per token or not at all.

## 1. Goals

1. People with little technical background use the departments from a browser. No install, no proprietary client.
2. One admin deploys, updates and tears down the stack with one guided command.
3. Idle cost close to the price of one small VM. Nothing that bills per hour while nobody is using it, except the VM.
4. Model hosting is a setting: pay-per-token APIs, the owner's home GPU, or an optional on-demand cloud GPU.
5. Separate accounts and data per user, an authenticator app and per-device credentials, invites gated by admin
   approval, guardrails on model calls.

Non-goals: high availability (one VM, restored from backup if it dies); replacing the local stack; auto-merge;
public self-signup.

## 2. Where the money went, and what replaces it

| First draft | Idle cost driver | Replacement | Why it is cheaper |
|---|---|---|---|
| Open WebUI, Authentik on Cloud Run, min 1 instance each | always-on vCPU and memory | containers on one VM | one VM is cheaper than two always-on Cloud Run services |
| Cloud SQL Postgres | always-on instance | Postgres container on the VM | no separate instance |
| HTTPS load balancer + Cloud Armor | forwarding rule and policy fees | Caddy on the VM (automatic Let's Encrypt), or a free Cloudflare Tunnel | no load balancer |
| Authentik (server + worker, ~2 GB RAM) | needs a larger VM | Authelia + LLDAP (~100 MB together) and a small invite service | fits a 4 GB VM |
| Phoenix | another service | LiteLLM JSONL logs, rotated to Cloud Storage; Phoenix optional on demand | nothing running |
| L4 GPU service as the default local tier | per-hour GPU | per-token APIs and the owner's home GPU by default; cloud GPU optional | $0 idle |
| Cloud Run Jobs per task | none (pay per use) | kept | already pay-per-use, mostly inside the free tier |

## 3. Architecture

```
Browser ── HTTPS ──▶ Caddy (TLS, rate limits)            [or Cloudflare Tunnel: no public IP, free WAF]
                      ├── auth.<domain>   ▶ Authelia (OIDC provider: TOTP, passkeys, brute-force bans)
                      │                        └── LLDAP (user directory, admin web UI)
                      ├── chat.<domain>   ▶ Open WebUI (OIDC client of Authelia; the only user-facing app)
                      └── admin.<domain>  ▶ invite/approval page, LiteLLM admin UI (admins only)
                                            │ models = six departments      │ tools = orchestrator MCP
                         ┌──────────────────┴───────────────┐               ▼
                         ▼                                  ▼        Orchestrator MCP ── Cloud Run Job per task
            LiteLLM gateway (internal)               Postgres (one database + role per service)
              guardrails, per-user keys, budgets, routing, fallbacks
        ┌─────────────┬─────────────────┼──────────────────────┐
  Vertex AI      open-model APIs      owner's home GPU        optional Cloud Run L4 GPU
  (Gemini Flash- (Qwen etc. via any   (Ollama on SEKAIHOME     (Ollama/vLLM, min 0;
   Lite / Flash)  OpenAI-compatible    over a tunnel; $0)       on demand only)
                  provider)

One VM: e2-medium (2 vCPU shared, 4 GB) + 2 GB swap, 20-30 GB balanced disk, Docker Compose.
Nightly: pg_dump + Open WebUI data + LLDAP + Authelia config ▶ Cloud Storage (versioned, 30-day lifecycle).
```

| Component | Where | Exposed | Notes |
|---|---|---|---|
| Caddy | VM | 443 only | automatic certificates; per-IP rate limits; security headers |
| Authelia | VM | via Caddy | OIDC provider for every app; two-factor required by policy for every domain |
| LLDAP | VM | admin domain only | users and groups; Authelia reads it over LDAP |
| Invite service | VM (part of the orchestrator package) | admin domain + invite links | section 4.2 |
| Open WebUI | VM | via Caddy | Postgres; embeddings from LiteLLM, not a local model, to save RAM; local login and signup off |
| LiteLLM | VM | internal only | Postgres turns on virtual keys, budgets and the admin UI |
| Orchestrator MCP | VM | internal only | validates Authelia tokens; jobs on Cloud Run Jobs |
| Postgres | VM | internal only | one database and login role per service |
| Job sandbox | Cloud Run Jobs | none | pay per run; deleted after each job |
| Cloud GPU (optional) | Cloud Run with L4, min 0, max 1 | internal, IAM-authenticated | only if the admin enables it |

Cheaper still: run the whole compose stack on the owner's machine and publish it through a Cloudflare Tunnel, with
Cloud Storage only for backups. Cloud cost is then about $0, but availability depends on the home PC being on, and
its RAM is already the binding constraint (`memory/state.md`). Supported as a profile, not the default.

### 3.1 Model hosts

Each LiteLLM tier is an `api_base` plus a key, so the deploy chooses per tier:

| Host profile | Idle cost | Data leaves the project |
|---|---|---|
| `vertex` (default for complex work) | $0, per token | no (Google-hosted, same project) |
| `home-gpu` (default for simple/medium when reachable) | $0 | leaves GCP to the owner's machine over an encrypted tunnel |
| `openai-compatible:<url>` | $0, per token | yes; admin marks it external |
| `gcp-gpu` (optional) | $0 at min 0; per second while running | no |

Default routing: simple and medium tiers go to `home-gpu`, falling back to a cheap Vertex model when the home machine
is off; complex tiers go to a stronger Vertex model. Groups can be restricted to in-project hosts (section 5.3).

### 3.2 Coding work without a local agent

Open WebUI cannot read or edit a user's local checkout. Coding tasks run server-side:

1. A user asks a department (in Open WebUI) to do a bounded task on a repository they connected.
2. The orchestrator starts a Cloud Run Job that clones the repo with that user's own git credential, runs the
   department agent through LiteLLM, and pushes a branch.
3. The user reviews the change and approves opening the PR from Open WebUI. Nothing merges automatically.

OpenHands (interactive web coding workspace) is out of scope: it needs more RAM than this VM has.

## 4. Identity and access

Authelia is the only sign-in and the OIDC provider for Open WebUI, the admin pages and the orchestrator. LLDAP holds
users and groups. Authentik remains the upgrade path if the built-in features below outweigh a larger VM.

### 4.1 Second factor and per-device credentials

- Two-factor is required by Authelia policy for every domain. On first sign-in a user must register a TOTP
  authenticator app (Google Authenticator, Aegis, 2FAS...) before reaching any app.
- Each device registers its own passkey (WebAuthn: Windows Hello, Touch ID, Android/iOS, security key). Users see and
  delete their registered passkeys in Authelia's settings page.
- Sessions are per device (a cookie per browser), 12 h idle / 7 d absolute for users, 1 h / 12 h for admins.
- Revoking a lost device: delete its passkey and, if it may hold a live session, reset the user's password, which
  ends all of that user's sessions. Authelia has no per-session list; this is the main trade-off against Authentik.
- Brute force: Authelia regulation bans a user/IP after repeated failures; Caddy rate-limits the sign-in endpoint.
- Admins: separate admin group, shorter sessions, passkey required. One break-glass admin in LLDAP with credentials
  sealed offline; its use raises an alert.

### 4.2 Invite and approval

Authelia has no self-registration, so a small invite service (part of the orchestrator package, ~200 lines) adds it:

```
member opens admin.<domain>/invite, enters invitee email ─▶ request stored (pending)
admins get an email ─▶ approve (pick group) | reject (inviter told)
on approval ─▶ service creates the user in LLDAP and emails a one-time set-password link (expires 72 h)
invitee sets password ─▶ first sign-in forces TOTP enrollment, then passkey for that device
first OIDC login creates the Open WebUI user
```

- Open WebUI keeps `DEFAULT_USER_ROLE=pending` as a second gate.
- Who can invite is a group; each inviter has a cap of open invites; optional allow-list of email domains.
- Email goes through any SMTP relay on port 587 (Google blocks outbound port 25).

### 4.3 Roles and groups

| Role | Can |
|---|---|
| admin | approve invites, manage groups, models, hosts, budgets; read audit log and traces |
| member | use the departments their groups allow; invite if permitted; manage own passkeys and data |
| pending | nothing until approved |

Groups (for example `devs`, `reviewers`, `docs-only`) come from LLDAP as an OIDC claim and map to Open WebUI groups,
which decide the departments, knowledge bases, tools and model hosts a user sees.

## 5. Data and context separation

### 5.1 Per service

| Service | Separation |
|---|---|
| Open WebUI | chats, memories, uploads and personal knowledge private per user; shared items granted to groups |
| Orchestrator | jobs, results and lessons carry the user's OIDC `sub`; queries filter on it; Postgres row-level security underneath |
| Job sandboxes | one Cloud Run Job per task, no shared disk; git credential from Secret Manager under that user's id only; files in `gs://<bucket>/users/<sub>/`; deleted after the job |
| LiteLLM | one virtual key per user with budget and rate limit; logs tagged with the user |
| Logs | contain every user's prompts: admins only, PII masked before writing, 30-day retention |
| Postgres | one database and login role per service; no service reads another's tables |

### 5.2 Orchestrator changes this requires

- Replace the single `ORCHESTRATOR_BEARER` with Authelia token validation (Open WebUI forwards the user's OAuth token
  to the MCP tool server).
- Move the job store from SQLite to Postgres with row-level security on `user_id`.
- Lessons per user by default; an admin promotes a lesson to shared. `memory/lessons.md` stays the local stack's file.
- Load department definitions from the package (generated from `agents/*.yaml`), not from a checkout.
- Gateway URL and model hosts come from configuration, not `127.0.0.1:4000`.
- Add the invite service (section 4.2).

### 5.3 Model host policy

Admins keep an allow-list of hosts with a data class (`in-project`, `owner-hardware`, `external`). A group can be
limited to `in-project`. LiteLLM rejects a request whose user may not reach the routed host, and fallbacks never move
to a less trusted class.

## 6. Safety

- Guardrails in LiteLLM: Presidio masks PII and secrets before any `external` host. Content screening uses a small
  Llama Guard-class model on the home GPU when reachable, else a Vertex safety check; never a model on the VM (no RAM).
- Side effects need a human: the orchestrator proposes branches and PRs; the user approves in Open WebUI.
- Limits: per-user budget and rate limit in LiteLLM; a project billing budget with alerts; Cloud GPU max 1 instance;
  job timeout and concurrency cap per user.
- Audit log: sign-ins and bans (Authelia), invites and approvals, role changes, delegated jobs, approvals of side
  effects and admin actions go to an append-only Postgres table and Cloud Logging.
- Host hardening: OS Login with two-factor for SSH (or SSH only through IAP), automatic security updates, only 443
  open (none with Cloudflare Tunnel), containers non-root, secrets in Secret Manager and read at start.
- User rights: export own data; account deletion removes chats, jobs, files, logs and the LiteLLM key after admin
  review.

## 7. Threat model

| Threat | Mitigation |
|---|---|
| Stolen password | TOTP required; passkey per device; Authelia bans; Caddy rate limits |
| Stolen or lost device | delete that device's passkey; password reset ends live sessions |
| Phishing of the second factor | passkeys are origin-bound; admins require passkeys |
| Uninvited signup | no self-registration; invite bound to email; admin approval; Open WebUI `pending` gate |
| Malicious or careless inviter | invite caps; admin approval; audit log names the inviter |
| User reads another user's data | per-user filters plus Postgres RLS; per-user storage prefixes and secrets; cross-user tests |
| Prompt injection through repo content or tool output | results treated as untrusted; guardrail scan; side effects need approval |
| Sensitive data sent to a third-party model | host allow-list with data class; Presidio; group restrictions; no fallback to a less trusted class |
| Runaway spend | per-user budgets; billing budget alerts; cloud GPU min 0, max 1; job caps |
| Single VM compromised | only 443 exposed; OS Login; updates; services internal; secrets not on disk in plain text; rebuild from Terraform + backup |
| VM or disk lost | nightly backups to versioned Cloud Storage; restore script; RPO 24 h, RTO about 1 h |
| Home GPU exposed | tunnel outbound-only from the home machine; LiteLLM is the only client; Ollama never public |

## 8. Monthly cost (rough, unverified; confirm in the Google Cloud pricing calculator)

| Item | Idle month | Notes |
|---|---|---|
| e2-medium VM, on demand | ~$25 | e2-small (~$12) if Open WebUI fits in 2 GB plus swap with API embeddings |
| Balanced disk 20-30 GB | ~$2-3 | |
| Static external IPv4 | ~$3-4 | $0 with Cloudflare Tunnel |
| Cloud Storage backups, logs, Secret Manager | ~$1 | |
| Cloud Run Jobs, Cloud Build | ~$0 | usually inside free tiers |
| **Idle floor** | **~$15-35** | was ~$100-200 |
| Model use | per token | Vertex / APIs; $0 on the home GPU; cloud GPU about $1 per hour only while running |

Further options: a VM schedule that stops it overnight (roughly halves the VM line, users lose night access); a
committed-use discount after usage is known; a Spot VM is not recommended (preemption logs everyone out).

## 9. One-command install for the admin

- README button "Open in Cloud Shell" clones the repo into Google's browser shell and starts `scripts/gcp-install.sh`.
- It asks for: project (new or existing), region, domain (or Cloudflare Tunnel), admin email(s), allowed email
  domains, SMTP relay, model host per tier, monthly budget.
- Terraform in `infrastructure/gcp/` creates: the VM with a startup script, firewall (443 only), static IP or no IP,
  service accounts, Secret Manager secrets, backup bucket with lifecycle, billing budget alert, and the optional GPU
  service.
- The VM startup script installs Docker, pulls pinned images and starts `infrastructure/gcp/compose.yaml`. The
  installer then imports the department models into Open WebUI, registers the orchestrator tool server, seeds LLDAP
  groups and creates the first admin (forced TOTP and passkey on first sign-in).
- Rerun to update; `scripts/gcp-install.sh destroy` tears down; `scripts/gcp-install.sh restore <date>` rebuilds from
  a backup.
- `stack.py build` gains a `gcp` target that writes the compose file, LiteLLM config, Open WebUI model files and the
  orchestrator department bundle.

## 10. Build order

1. Orchestrator changes from section 5.2, tested locally (token validation, per-user jobs, Postgres, invite service).
2. Compose stack (Caddy, Authelia, LLDAP, Open WebUI, LiteLLM, orchestrator, Postgres) running on the local machine.
3. Terraform for the VM, secrets, backups and budget; Cloud Run Jobs sandbox.
4. Model hosts: `vertex` first, then `home-gpu` over a tunnel, then optional `gcp-gpu`.
5. Guardrails, budgets, audit log, backup and restore drill.
6. Cloud Shell installer, destroy and restore paths, README.
7. Cross-user access tests and a review by the `security` department before inviting anyone.

## 11. Open decisions

1. Public IP with Caddy, or Cloudflare Tunnel (no IP, free WAF, but a third-party service in the path).
2. e2-medium or e2-small; measure Open WebUI's memory with API embeddings first.
3. Whether the home GPU serves other users at all (it must be on, and their prompts reach the owner's machine).
4. Whether user data may ever reach `external` hosts.
5. Authelia + LLDAP + invite service (cheap, some custom code, no per-session list) or Authentik (built in, needs
   roughly double the VM).
6. Domain, region, first admins, allowed email domains, SMTP relay.
