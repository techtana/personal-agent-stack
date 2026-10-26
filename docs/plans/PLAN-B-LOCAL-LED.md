# Plan B: local-led mixture

The local server is the main processor: SEKAIHOME by default, or any machine with a `machines/<host>.yaml` profile.
Simple and medium work runs on the local GPU. Complex and reasoning work may go to a cloud API, but only after the
privacy gate has confirmed that the request carries no personal data, secrets or sensitive topics. Sensitive requests
always stay local, at every complexity tier.

Prerequisite reading: `SHARED-COMPONENTS.md` (S1-S7). This plan builds on the existing native stack (`stack.py up`,
the tray app, Ollama, LiteLLM, the orchestrator and Open WebUI as described in `docs/ORCHESTRATOR-DESIGN.md`).

## 1. Topology

```
Remote and LAN users                              Owner on the local machine
      │ HTTPS                                      │ Claude Code profile B (claude-local) / OpenCode
      ▼                                            │
Edge VM (e2-micro, optional, see 1.1)              │
 ├─ auth.<domain>: Caddy + Authelia + LLDAP + invites   (S5; TLS ends here, sees no chat content)
 └─ chat.<domain>: nginx stream, SNI passthrough ──WireGuard (home dials out)──┐
                                                                               ▼
Local server (SEKAIHOME), native services managed by stack.py / tray:
  Caddy (TLS for chat.<domain>) ─▶ Open WebUI + privacy_notice filter (S3)
                                     ▼
  LiteLLM + privacy_hook (S2) ──▶ gate service (S1)
   │ sensitive, any tier, or simple/medium      │ not sensitive and complex/reasoning
   ▼                                            ▼
  Ollama on the local GPU (private)            external API (Anthropic by default; data_class external)
  Orchestrator MCP (S6), Postgres (native; LiteLLM spend per user, admin UI)
```

### 1.1 Access modes

| Mode | Who can use it | Cloud needed |
|---|---|---|
| `owner` | the owner on this machine only; no identity layer (today's setup plus the gate) | none |
| `edge` (default for several users) | invited users anywhere, through the edge VM | e2-micro VM |

In `edge` mode the edge VM terminates TLS only for `auth.<domain>`. Chat traffic for `chat.<domain>` passes through
as encrypted TCP (SNI routing) to Caddy on the local server, so the edge VM never sees prompts or answers. The local
server dials out over WireGuard, so no port is opened on the home router. When the local server is off, the edge
serves a "the server is offline" page.

## 2. Routing rules

| Request | Gate verdict | Action |
|---|---|---|
| simple / medium tier | any | local (`<dept>-local`) |
| complex / reasoning tier | not sensitive | `<dept>-cloud` (external) when a cloud key is configured, else local |
| complex / reasoning tier | sensitive | local `sensitive_target` (default `<dept>-local`), fallbacks off, alert "kept on the local server; quality may be lower" |
| explicit `cloud-*` or `<dept>-cloud` request (orchestrator `tier=cloud`, Claude Code profile B `opus_model`) | sensitive | rewritten to local (`explicit_cloud_on_sensitive: local`), or refused if set to `refuse` |
| sensitive, longer than the local context (`primary_num_ctx`) | - | reply asking to shorten or split; the existing `context_window_fallbacks` to `cloud-default` are blocked for it |
| not sensitive, local Ollama down | - | complex goes to cloud as usual; simple/medium go to `cloud-cheap` only if `cloud_fallback_for_nonsensitive: true` (default true) |
| sensitive, local Ollama down | - | error "the local model is unavailable"; never cloud |
| embeddings | any | local (`private-embed` from the gate, or `local-embed` from Ollama) |
| gate error or timeout | - | treated as sensitive, so it stays local |
| "<Department> (local only)" model in Open WebUI | - | local, whatever the verdict |

Policy additions in `policy/privacy.yaml` for this plan:

```yaml
actions:
  on_sensitive: private
  on_private_unavailable: refuse
  sensitive_target: dept-local            # or local-reviewer when a larger local model is pulled
  explicit_cloud_on_sensitive: local      # local | refuse
  cloud_fallback_for_nonsensitive: true
```

### 2.1 Claude Code coverage

- Profile B (`scripts/claude-local.ps1|sh`) goes through LiteLLM `/v1/messages`, so the gate covers every prompt and
  tool result.
- Profile A (Claude Code on the subscription) talks to Anthropic directly, and the gateway cannot see it.
  Optional package B6 adds a `UserPromptSubmit` hook that calls the gate and blocks a sensitive prompt with "use
  claude-local for this". It cannot scan file contents that Claude Code's tools read later. Rule of thumb in the user
  guide: work on sensitive repositories in profile B.

## 3. Work packages

Shared packages S1-S4, S6 and S7 are needed in every mode; S5 only in `edge` mode. Plan-specific packages:

| # | Package | Size | Depends on |
|---|---|---|---|
| B0 | Decisions (section 6): access mode, cloud provider and key, domain and SMTP for `edge` | S | - |
| B1 | Build: `sensitive_target`, `explicit_cloud_on_sensitive`, "(local only)" Open WebUI models, `data_class` on the existing `local-*`, `<dept>-local`, `cloud-*`, `<dept>-cloud` deployments | S | S4 |
| B2 | Native services: add `gate` and `postgres` to `scripts/stacklib/services.py` (start, stop, status, pid plus start time) and to the tray; install the LiteLLM tool with `--with-editable packages/privacy-gate`; setup generates `DATABASE_URL` and `GATE_BEARER` in `.env`; Postgres from winget (`PostgreSQL.PostgreSQL.17`) on Windows, the distro package on Linux | M | S1, S2 |
| B3 | Edge VM (`edge` mode): Terraform `infrastructure/edge-gcp/` (e2-micro, static IP, firewall 80/443 tcp and 51820 udp, no other services), nginx stream SNI passthrough for `chat.<domain>` (ports 80 and 443), Caddy for `auth.<domain>`, S5 bundle, WireGuard hub, offline page | M | S5 |
| B4 | Local side of `edge` mode: WireGuard client config from `stack.py wg-config`; Caddy for Windows terminating `chat.<domain>` (ACME HTTP-01 through the passthrough) and serving Open WebUI on 3000; Windows Firewall allowing 443 only from the tunnel; Open WebUI OIDC to Authelia plus the S3 lock-down settings | M | B3 |
| B5 | `stack.py install --mode local-led [--access owner|edge]`, extending the one-stop installer proposal: prerequisites, pinned tools, gate, Postgres, build, tray with start at login, smoke test plus `gate-eval`, and the edge VM through `gcloud` when chosen | M | B1-B4 |
| B6 | Optional: Claude Code `UserPromptSubmit` gate hook for profile A (section 2.1) | S | S1 |
| B7 | Tests (section 4) and the user guide | M | all |

Suggested order: B0 -> S1, S7 -> S2, S4, B1 -> B2 -> S3 -> (owner mode is usable here) -> S6 -> S5, B3, B4 -> B5 ->
B6 -> B7.

## 4. Acceptance tests

1. Leak canary (S7) against the local gateway: 0 sensitive requests reach the external mock across every route,
   including `tier=cloud` from the orchestrator, `/v1/messages` with `opus_model` mapped to cloud, and a
   context-window overflow.
2. A sensitive reasoning-tier request is answered by the local model with the "kept local" notice; the audit row says
   `private/local`.
3. A non-sensitive complex request goes to the cloud tier, and its audit row carries a non-sensitive verdict.
4. Gate service stopped: every request is served locally (fail closed), and the tray shows the gate as down.
5. Gate overhead p95 <= 50 ms on SEKAIHOME; the gate stays within its memory target while the 9B primary is loaded.
6. `edge` mode: the edge VM's nginx and Caddy logs contain no prompt or answer text (TLS passthrough checked with a
   capture on the VM); invite -> approval -> TOTP -> passkey works; with the local server off, the offline page
   shows.
7. Cross-user: user B cannot read user A's jobs or chats.
8. `stack.py install` on a clean Windows user account finishes with smoke and `gate-eval` green.

## 5. Cost (rough, unverified)

| Item | Month |
|---|---|
| Local server | $0 cloud (the owner's hardware and electricity) |
| Edge VM (`edge` mode) | ~$0-5: e2-micro is in the free tier in some US regions; the static IPv4 may still be billed |
| External API | per token, only for non-sensitive complex and reasoning work |
| **Idle floor** | **$0 (`owner`) or ~$0-5 (`edge`)** |

## 6. Decisions needed before B0

| # | Decision | Default if not decided |
|---|---|---|
| B-D1 | Access mode | `owner` first, then `edge` when the first other user is invited |
| B-D2 | Cloud provider and key for complex work | Anthropic (`ANTHROPIC_API_KEY`), tiers as in `machines/_defaults.yaml` |
| B-D3 | Local model for sensitive complex work | `<dept>-local` (qwen3.5:9b); revisit the 35B MoE after a RAM upgrade (`memory/state.md`) |
| B-D4 | Explicit cloud requests that turn out sensitive | rewrite to local |
| B-D5 | Domain, DNS provider and SMTP relay (`edge` mode) | none; required for `edge` |
| B-D6 | Build B6 (the Claude Code profile A prompt hook)? | yes, as a warning hook |

## 7. Risks

| Risk | Mitigation |
|---|---|
| The gate misses something and it goes to the cloud | layered detectors, fail closed, S7 recall gate, "(local only)" models, audit review in the weekly retro |
| Sensitive complex work gets weaker answers locally | the notice says so; users can split the task; a larger local model after a RAM upgrade |
| The home server is the single point of failure | offline page at the edge; start at login through the tray; the owner's machine already runs the stack daily |
| More services on SEKAIHOME (gate, Postgres) squeeze RAM | gate memory target <= 600 MB; Postgres with small `shared_buffers`; measured in test 5 |
| Users on profile A Claude Code bypass the gate | B6 warning hook; user guide; only the owner uses Claude Code |
