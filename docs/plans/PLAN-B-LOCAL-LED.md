# Plan B: local-led mixture

Revised 2026-10-26: native runtime (Harbor optional, not installed), broader privacy gate (profiling, media),
orchestrator removed, MCP server and skill for other apps.

The local server is the main processor: SEKAIHOME by default, or any machine with a `machines/<host>.yaml` profile.
Simple and medium work runs on the local GPU. Complex and reasoning work may go to a cloud API, but only after the
local privacy gate confirms the request carries no personal or profilable information, secrets, or media showing
people. Sensitive requests stay local at every tier.

Prerequisites: `SHARED-COMPONENTS.md` (S1-S8, R), `INSTALL.md` (section 2.1).

## 1. Topology

```
Remote and LAN users                                  Owner on this machine
      │ HTTPS                                          │ Claude Code (profile B via LiteLLM: enforced;
      ▼                                                │   profile A: privacy-gate MCP + skill + hooks, advisory)
Edge VM (e2-micro, `edge` mode only)                   │ OpenCode, Continue (LiteLLM: enforced)
 ├─ auth.<domain>: Caddy + Authelia + LLDAP + invites (S7)
 └─ chat.<domain>: nginx stream, SNI passthrough ──WireGuard (home dials out)──┐
                                                                               ▼
SEKAIHOME (native runtime: stack.py up / tray, no Docker)
 ├─ Ollama (GPU)  ◀──────────────────────────────────────────────┐ private
 ├─ Open WebUI + filter (S4), LiteLLM + privacy_hook (S3) ───────┤
 ├─ privacy-gate (S1-S2, MCP S5), PostgreSQL                     │ not sensitive and complex/reasoning
 └─ Caddy for chat.<domain> (`edge` mode)                         └─▶ external API, identifiers stripped
```

Harbor can replace the native runtime later (`INSTALL.md` section 4); nothing in this plan depends on it.

### 1.1 Access modes

| Mode | Users | Cloud |
|---|---|---|
| `owner` | the owner on this machine; no identity layer | none |
| `edge` | invited users anywhere | e2-micro edge VM |

In `edge` mode the edge terminates TLS only for `auth.<domain>`. Chat traffic passes through encrypted (SNI routing)
to Caddy on SEKAIHOME, so the edge never sees prompts, answers or media. SEKAIHOME dials out over WireGuard; no router
port is opened. When SEKAIHOME is off, the edge shows an offline page.

## 2. Routing rules

| Request | Gate verdict | Action |
|---|---|---|
| simple / medium tier | any | local `<dept>-local` |
| complex / reasoning tier | not sensitive | `<dept>-cloud` when a key is configured, else local |
| complex / reasoning tier | sensitive | local `sensitive_target`, fallbacks off, alert "kept on this server; answers may be weaker" |
| explicit `cloud-*` / `<dept>-cloud` from any client | sensitive | rewritten to local (`explicit_cloud_on_sensitive: local`) or refused |
| image, video, audio | media with people, documents, voice or location metadata | local vision model; `redact_then_external` only if enabled |
| category with `generalize` enabled | sensitive | local rewrite shown to the user, then external |
| sensitive, longer than the local context | - | reply asking to shorten or split; existing `context_window_fallbacks` to cloud blocked for it |
| not sensitive, Ollama down | - | complex goes to cloud; simple/medium to `cloud-cheap` if `cloud_fallback_for_nonsensitive: true` |
| sensitive, Ollama down | - | error "the local model is unavailable"; never cloud |
| embeddings | any | `private-embed` |
| gate error or unscannable file | - | treated as sensitive, so local |
| "<Department> (local only)" model | - | local |

```yaml
# policy/privacy.yaml additions for this plan
actions:
  on_sensitive: private
  on_private_unavailable: refuse
  sensitive_target: dept-local            # or a larger local model when one is pulled
  explicit_cloud_on_sensitive: local
  cloud_fallback_for_nonsensitive: true
```

### 2.1 Coverage by app

| App | How it is covered | Strength |
|---|---|---|
| Open WebUI | through LiteLLM; filter shows alerts; MCP tools available | enforced |
| Claude Code profile B (`claude-local`), OpenCode, Continue | through LiteLLM | enforced |
| Claude Code profile A (subscription), Claude Desktop | privacy-gate MCP + `privacy-check` skill + `UserPromptSubmit` / `PreToolUse` hooks | advisory: cannot see file contents the app reads and sends to its own cloud model |

User guide rule: sensitive work belongs in Open WebUI or Claude Code profile B.

## 3. Work packages

| # | Package | Size | Depends on |
|---|---|---|---|
| B0 | Decisions (section 6) | S | - |
| S1-S6, S8 | shared gate, hook, Open WebUI, MCP and skill, build, evals | see shared file | - |
| B1 | Build: `sensitive_target`, `explicit_cloud_on_sensitive`, "(local only)" models, `data_class` on the existing `local-*`, `<dept>-local`, `cloud-*`, `<dept>-cloud` deployments, a local vision deployment | S | S6 |
| B2 | Native services: privacy-gate in `services.py` and the tray; PostgreSQL install and databases in setup; LiteLLM tool reinstalled `--with-editable packages/privacy-gate`; ffmpeg check | M | S2, S3 |
| B3a | `stack.py install --mode local-led [--access owner|edge]`: the `INSTALL.md` 2.1 and 3 steps with checks and prompts; ends with smoke and gate-eval | M | B1, B2 |
| B3 | Edge VM (`edge` mode): Terraform `infrastructure/edge-gcp/` (e2-micro, static IP, firewall 80/443/tcp and 51820/udp), nginx SNI passthrough, Caddy for `auth.<domain>`, S7, WireGuard hub, offline page | M | S7 |
| B4 | SEKAIHOME side of `edge`: WireGuard client (`stack.py wg-config`), Caddy for Windows serving `chat.<domain>`, Windows Firewall rule limiting 443 to the tunnel, Open WebUI OIDC | M | B3 |
| B5 | Tests (section 4) | M | all |
| R | Remove redundant parts (shared file section 3) | S | B5 |
| B6 | User guide | S | B5 |

Order: B0 -> S1, S1b, S8 -> S2, S3, S6, B1 -> B2 -> S4, S5 (`owner` mode usable here) -> R -> B3a -> S7, B3, B4 ->
B5 -> B6. R can run as soon as the privacy-gate MCP server replaces the orchestrator.

## 4. Acceptance tests

1. Leak canary (S8) against the local gateway: 0 sensitive requests or media reach the external mock on any route,
   including explicit cloud aliases, `/v1/messages` and context overflow.
2. External requests carry no user identifiers (checked at the mock).
3. A sensitive reasoning-tier request is answered locally with the notice; audit `private/local`.
4. A non-sensitive complex request goes to the cloud tier with a non-sensitive verdict in its audit row.
5. A screenshot containing a face or an ID card stays local; a code screenshot with no people or personal text may go
   external.
6. privacy-gate stopped: every request served locally (fail closed).
7. Gate overhead p95 <= 50 ms for text on SEKAIHOME; privacy-gate plus PostgreSQL stay under 1.2 GB resident with
   the 9B loaded in Ollama.
8. Claude Code profile A: the hook blocks a prompt with a fake card number and points to profile B; the skill makes
   Claude call `check_text` before a `WebSearch` that contains personal details.
9. `edge` mode: edge logs contain no prompt text (capture on the VM); invite -> approval -> TOTP -> passkey works;
   offline page shows when SEKAIHOME is off.
10. `stack.py install` on a clean Windows user account ends with smoke and gate-eval green.

## 5. Cost (rough, unverified)

| Item | Month |
|---|---|
| SEKAIHOME | $0 cloud |
| Edge VM (`edge` mode) | ~$0-5 (e2-micro free tier in some US regions; static IPv4 may be billed) |
| External API | per token, non-sensitive complex work only |
| **Idle floor** | **$0 (`owner`) or ~$0-5 (`edge`)** |

## 6. Decisions

| # | Decision | Default |
|---|---|---|
| B-D1 | Access mode | `owner` first; `edge` when the first other user is invited |
| B-D2 | Cloud provider and key | Anthropic, tiers from `machines/_defaults.yaml` |
| B-D3 | Local model for sensitive complex work | `<dept>-local` (qwen3.5:9b) |
| B-D4 | Local vision model | chosen in the S1 spike; must share 12 GB VRAM with the 9B or swap in on demand |
| B-D5 | Explicit cloud requests that turn out sensitive | rewrite to local |
| B-D6 | Domain, DNS provider, SMTP (`edge`) | required for `edge` |
| B-D7 | Runtime | `native`; Harbor optional later (not installed) |

## 7. Risks

| Risk | Mitigation |
|---|---|
| Gate misses something and it goes to the cloud | layered detectors, fail closed, S8 recall gate, "(local only)" models, audit review |
| Weaker answers for sensitive complex work | notice says so; users split tasks; larger local model after a RAM upgrade |
| New native services (gate, PostgreSQL) add RAM pressure | memory targets in S1 and test 7; PostgreSQL `shared_buffers=128MB`; revisit if the 35B primary returns |
| SEKAIHOME is a single point of failure | offline page; start at sign-in; daily use already depends on it |
| Claude Code profile A bypasses enforcement | skill, MCP and hooks warn; user guide; only the owner uses it |
| A LiteLLM or Open WebUI upgrade changes hook or settings behaviour | versions pinned in setup; S8 canary before upgrades |
