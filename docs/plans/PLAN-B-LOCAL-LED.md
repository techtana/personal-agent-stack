# Plan B: local-led, private first

Revised 2026-10-26: every tier runs locally; external APIs optional, off by default, and only by intentional user
choice; native runtime (Harbor optional, not installed); no add-ons for clients outside the privacy boundary.

The local server is the main processor: SEKAIHOME by default, or any machine with a `machines/<host>.yaml` profile.
Every department and complexity tier runs on the local GPU. External APIs (Anthropic, Vertex AI, Hugging Face and
others) can be enabled by an admin and used only as described in `SHARED-COMPONENTS.md` section 2: explicit model
choice, per-user opt-in, per-conversation consent, and the local gate refusing anything sensitive.

Prerequisites: `SHARED-COMPONENTS.md`, `INSTALL.md` section 2.1.

## 1. Topology

```
Remote and LAN users
      │ HTTPS (end to end to SEKAIHOME)
      ▼
Edge VM (e2-micro, `edge` mode only): pure TCP relay (SNI passthrough) for auth.<domain> and chat.<domain>;
      │ terminates nothing, stores nothing; WireGuard to SEKAIHOME (home dials out)
      ▼
SEKAIHOME (native runtime: stack.py up / tray, no Docker)
 ├─ Caddy (TLS for both domains)
 ├─ Keycloak (S7, native through Java)                     (B-S0 confirms it as a Windows service)
 ├─ Open WebUI + filter (S4)
 ├─ LiteLLM + privacy guardrail (S3) ──▶ Ollama (GPU): every tier, media, titles
 ├─ privacy-gate (S1-S2), PostgreSQL                       ┆ external (off by default; explicit,
 └─ trace hooks, retro                                      ┆ consented, non-sensitive only)
                                                            └┄▶ Anthropic · Vertex AI · Hugging Face · …
```

Keycloak ships an official Windows service install but needs about 1.3-1.5 GB of RAM (V7). If that does not fit the RAM budget in B-S0, identity moves to a Confidential VM at the edge
(n2d, ~$60 a month), which then terminates TLS for `auth.<domain>` only; chat stays end to end to SEKAIHOME.

### 1.1 Access modes

| Mode | Users | Cloud |
|---|---|---|
| `owner` | the owner on this machine; no identity layer | none |
| `edge` | invited users anywhere | e2-micro relay (sees only encrypted traffic) |

When SEKAIHOME is off, the relay has nothing to forward and the browser shows a connection error; an offline page
would need TLS at the edge, which this plan avoids.

## 2. Routing

| Request | Action |
|---|---|
| department or "(private)" model, any tier | local `<dept>-local` (or a larger local model when pulled) |
| media | local vision model |
| embeddings, titles, tags | local (`private-embed`, private aliases) |
| longer than the local context | reply asking to shorten or split |
| Ollama down | "the local model is unavailable"; never external |
| external model chosen, all conditions met, verdict not sensitive | that provider, identifiers stripped |
| external model chosen, verdict sensitive | refused, categories named, one-click resend to the local model |
| external model without grant, opt-in or consent, or gate unhealthy | refused |

### 2.1 Clients

| Client | Status |
|---|---|
| Open WebUI | inside the boundary; the user surface |
| OpenCode, Continue (gateway as the only endpoint, configs generated) | inside the boundary |
| Claude Code profile B (`claude-local`) | owner development tool: model calls gated; non-essential traffic off; `WebFetch` and `WebSearch` denied; not offered to users |
| Claude Code profile A (subscription), Claude Desktop, vendor apps | outside the boundary; no skills, hooks or MCP add-ons are provided for them |

## 3. Work packages

| # | Package | Size | Depends on |
|---|---|---|---|
| B0 | Decisions (section 6) | S | - |
| B-S0 | Spike: Keycloak as a native Windows service (RAM, device activity, invite plus admin enablement: V7); Caddy for Windows with TLS for two domains; `winget configure` with Smart App Control (V9) | S | - |
| S1-S4, S6, S8 | shared gate, guardrail, Open WebUI, build, evals | see shared file | - |
| B1 | Build: private-only department routers; local vision deployment; "(private)" models; external aliases only when enabled | S | S6 |
| B2 | Native services: privacy-gate in `services.py` and the tray; PostgreSQL install and databases in setup; LiteLLM tool reinstalled `--with-editable packages/privacy-gate`; ffmpeg check. The native manager stays as is for `owner` mode | M | S2, S3 |
| B2b | Supervision for `edge` mode: Task Scheduler "at startup" tasks with restart on failure (services run before sign-in); keep the launch helper (uv tool `python.exe` start, `.env`, logs) and `stack.py status`; drop pid files and the tray's supervisor role (tray stays as an optional status viewer). On Linux, generate systemd units instead of finishing the untested native code | M | B2 |
| R | Remove redundant parts (shared file section 5) | S | B2 |
| B3 | `stack.py install --mode local-led [--access owner|edge]`: `INSTALL.md` 2.1 and 3 with checks and prompts; ends with smoke and gate-eval | M | B1, B2 |
| S7 | Identity: **Keycloak** on SEKAIHOME (or a confidential edge VM per B-S0) | M | B-S0 |
| B4 | Edge relay (`edge` mode): Terraform `infrastructure/edge-gcp/` (e2-micro, static IP, firewall 80/443/tcp, 51820/udp), nginx stream SNI passthrough for both domains, WireGuard hub; SEKAIHOME WireGuard client (`stack.py wg-config`) and Windows Firewall rule limiting 443 to the tunnel | M | S7 |
| B5 | Tests (section 4) | M | all |
| B6 | User guide: the privacy boundary, alerts, external consent | S | B5 |

Order: B0 -> S1, S1b, S8 -> S2, S3, S6, B1 -> B2 -> R -> S4 (`owner` mode usable here) -> B3 -> B-S0 -> S7, B2b, B4 ->
B5 -> B6.

## 4. Acceptance tests

1. With `external.enabled: false`, the leak canary mock receives nothing on any route, including `/v1/messages` from
   Claude Code profile B and context overflow.
2. With external enabled: no sensitive request, nothing without grant, opt-in or consent, nothing while the gate is
   down, nothing via fallback, and no user identifiers reach the mock.
3. Every department alias and tier is served by a local deployment (audit rows `private/onprem`).
4. A screenshot with a face or an ID card is processed locally; with external chosen, it is refused.
5. privacy-gate stopped: local requests still work; external requests are refused.
6. Gate overhead p95 <= 50 ms for text; privacy-gate plus PostgreSQL under 1.2 GB resident with the 9B loaded.
7. Claude Code profile B: telemetry and web tools are off (checked with a network capture during a session).
8. `edge` mode: a capture on the relay shows only TLS; invite -> approval -> TOTP -> passkey works.
9. Cross-user: user B cannot read user A's chats or consents.
10. `stack.py install` on a clean Windows user account ends with smoke and gate-eval green.

## 5. Cost (rough, unverified)

| Item | Month |
|---|---|
| SEKAIHOME | $0 cloud |
| Edge relay (`edge` mode) | ~$0-5 (e2-micro free tier in some US regions; static IPv4 may be billed) |
| Confidential edge VM (only if identity cannot run on Windows) | ~$60 |
| External APIs (optional) | per token |
| **Idle floor** | **$0 (`owner`) or ~$0-5 (`edge`)** |

## 6. Decisions

| # | Decision | Default |
|---|---|---|
| B-D1 | Access mode | `owner` first; `edge` when the first other user is invited |
| B-D2 | External models | disabled; if enabled, which providers and which groups |
| B-D3 | Local models per tier and for media | qwen3.5:9b for all tiers; vision model chosen in the S1 spike (shares 12 GB VRAM or swaps in) |
| B-D4 | Domain, DNS provider, SMTP (`edge`) | required for `edge` |
| B-D5 | Runtime | `native`; Harbor optional later (not installed) |

## 7. Risks

| Risk | Mitigation |
|---|---|
| Weaker answers than cloud models for complex work | larger local model after a RAM upgrade; the owner can enable external models for non-sensitive work, deliberately |
| Gate false negatives once external is enabled | off by default; consent per conversation; S8 recall gate; audit review |
| SEKAIHOME is a single point of failure | start at sign-in through the tray; daily use already depends on it |
| New native services add RAM pressure | memory targets in S1 and test 6; PostgreSQL `shared_buffers=128MB` |
| Identity components lack Windows builds | B-S0 first; confidential edge VM as the fallback |
| A LiteLLM or Open WebUI upgrade changes hook or settings behaviour | versions pinned in setup; S8 canary before upgrades |
