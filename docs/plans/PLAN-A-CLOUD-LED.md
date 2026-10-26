# Plan A: cloud-led, private first

Revised 2026-10-26: private models first, on confidential cloud servers that the cloud provider cannot read; external
APIs optional, off by default, and only by intentional user choice.

The stack runs in our own Google Cloud project on Confidential VMs. Every request is processed by private models:
first on a confidential model server in the project, then on the on-prem machine, and if neither is available the
request waits in an encrypted queue. Memory is encrypted by the CPU and checked by attestation; disks and backups are
encrypted under keys held outside Google. External APIs (Anthropic, Vertex AI, Hugging Face and others) can be
enabled by an admin and used only as described in `SHARED-COMPONENTS.md` section 2.

Prerequisites: `SHARED-COMPONENTS.md`, `INSTALL.md` section 2.2.

## 1. What "the provider cannot access or decrypt" means here

| Layer | Protection | Who holds the key |
|---|---|---|
| Memory in use (main VM, model server) | AMD SEV-SNP or Intel TDX Confidential VMs; NVIDIA H100 confidential computing on the GPU option | the CPU or GPU, per VM; not readable by the hypervisor or Google operators |
| Proof of the above | remote attestation report checked before any key is released | verified by our key broker |
| Disks (data, model weights) | LUKS inside the VM | our key broker (OpenBao on owned hardware); released only to an attested VM, or entered by an admin |
| Backups | restic, encrypted before upload to Cloud Storage | the same broker; a copy sealed offline by the admin |
| Traffic | TLS ends inside the confidential VM (no Google load balancer); WireGuard between our hosts | the VMs |
| App secrets | on the encrypted disk or in the broker; not in Google Secret Manager | us |
| Logs sent to Google | metadata only (no prompts, answers or file names); serial console off | - |

What remains trusted, stated in the user guide: the CPU and GPU vendors' hardware roots of trust, the measured guest
firmware (checked by attestation), and protection against side-channel attacks. Google can still stop or delete VMs
(availability), but not read them.

## 2. Topology

```
Browser ─TLS ends inside the VM─▶ Main VM: Confidential VM (N2D, AMD SEV-SNP), Docker Compose
                                    Caddy · Authelia + LLDAP + invites (S7) · Open WebUI + filter (S4)
                                    LiteLLM + privacy_hook (S3) · privacy-gate (S1-S2, MCP S5, queue, controller)
                                    PostgreSQL · WireGuard hub · LUKS data disk
          private, by priority      │
          ┌─────────────────────────┼──────────────────────────────┐
          ▼                         ▼                              ▼
  Confidential model server   On-prem: SEKAIHOME            Deferred queue (encrypted)
  (C3 + Intel TDX on CPU,     Ollama over WireGuard          when no private host is up
   or A3 + H100 CC on GPU)
  started on demand,
  stopped when idle
          ┆ external (off by default; explicit, consented, non-sensitive only)
          └┄▶ Anthropic API · Vertex AI · Hugging Face · OpenAI-compatible
Key broker: OpenBao on owned hardware (SEKAIHOME or the admin's machine), reached over WireGuard.
Backups: restic -> Cloud Storage, encrypted client-side.
```

## 3. Private model hosts

| Option | Machine (to confirm in A-S0) | Fits | Speed | Cost while running (rough) | Default |
|---|---|---|---|---|---|
| `confidential-cpu` | C3 with Intel TDX and AMX, 8-22 vCPU | 4-9B quantised text models | to measure in A-S0 (CPU inference) | ~$0.4-1 per hour | first |
| `confidential-gpu` | A3 with one H100 in confidential-computing mode | large and vision models | fast | ~$10+ per hour | off; for heavy work, started deliberately by an admin or a scheduled window |
| `onprem` | SEKAIHOME over WireGuard | 9B now (52 tok/s), 35B MoE | measured | $0 | second |

```yaml
# machines/<main-vm>.yaml (class cloud-first, runtime compose)
deployment: cloud-led
private_hosts:                       # tried in this order
  - {name: confidential-cpu, kind: llama-cpp, instance: private-model-1, zone: <zone>, model: <9B GGUF>,
     idle_stop_minutes: 20, start_timeout_s: 300}
  - {name: onprem, kind: ollama, url: http://10.66.0.2:11434, model: qwen3.5:9b, vision_model: <local vision model>}
  # - {name: confidential-gpu, kind: vllm, instance: private-gpu-1, zone: <zone>, model: <large model>, manual_start: true}
```

The controller in privacy-gate starts a stopped model server through the Compute API when a request needs it (its
service account may start and stop only those instances), waits for attestation, disk unlock and model load (the
filter shows "starting the private server"), and stops it after `idle_stop_minutes`. If the start fails or times
out, the next host is tried; if none is available, the request is queued. Media goes to the first host with a vision
model (on-prem by default; the CPU option is too slow for vision).

## 4. Routing

| Request | Action |
|---|---|
| department or "(private)" model, any tier | private host order: `confidential-cpu` -> `onprem` -> queue; `confidential-gpu` when started and the tier is complex/reasoning |
| media | first private host with a vision model, else queue |
| embeddings, titles, tags | privacy-gate and private aliases on the main VM |
| external model chosen, all conditions met, verdict not sensitive | that provider, identifiers stripped |
| external model chosen, verdict sensitive | refused, categories named, one-click resend to the private model |
| external model without grant, opt-in or consent, or gate unhealthy | refused |
| private request longer than the private model's context | reply asking to shorten or split; never external |

### 4.1 Deferred queue (in privacy-gate)

Table `deferred_requests` in PostgreSQL on the encrypted disk: `id` (`Q-…`), `user_id`, `chat_id` (if forwarded),
`model`, `request_enc` / `result_enc` (AES-256-GCM, key from the broker, nonce per row), `status` (`queued`, `running`,
`done`, `failed`, `expired`, `cancelled`), `attempts`, timestamps, `error`.

1. The hook calls `POST /internal/deferred` and replies at once: "Queued as Q-1234: no private server is available
   right now…".
2. The worker replays FIFO per user when a private host is up (starting `confidential-cpu` if allowed), with header
   `x-privacy-replay: <id>`; the hook allows replays to private deployments only.
3. Delivery: an email without content; MCP tools `list_deferred`, `get_deferred`, `cancel_deferred` in Open WebUI.
4. Limits: 20 per user, 500 total, 25 MB per request; expiry 72 h; results deleted 7 days after delivery.

## 5. Work packages

| # | Package | Size | Depends on |
|---|---|---|---|
| A0 | Decisions and accounts (section 8) | S | - |
| A-S0 | Spike: Confidential VM types per region (N2D SEV-SNP, C3 TDX, A3 H100 CC); attestation tooling for each; 9B tokens/s on C3 TDX with llama.cpp; cold start (boot + attestation + unlock + model load) | S | A0 |
| S1-S6, S8 | shared gate, hook, Open WebUI, MCP, build, evals | see shared file | - |
| A1 | Build target `deployment: cloud-led`: private host groups, `infrastructure/compose/cloud-led.yaml` (Caddy, identity, Open WebUI, LiteLLM, privacy-gate, PostgreSQL) | M | S6 |
| A2 | Terraform `infrastructure/gcp/`: Confidential VMs (main and model server), firewall (443/tcp, 51820/udp), static IP, a service account limited to starting and stopping the model servers, billing budget alert, no Secret Manager for app secrets | M | A-S0 |
| A3 | Key broker and encryption: OpenBao on owned hardware; attestation verification; LUKS unlock at boot over WireGuard; manual admin unlock as fallback; restic backups with off-Google keys; restore script | L | A2 |
| A4 | Confidential model server image: llama.cpp (CPU) or vLLM (GPU option), weights on the LUKS disk; controller in privacy-gate (start on demand, idle stop, health) | M | A2, A3 |
| A5 | On-prem link: WireGuard hub; `stack.py wg-config` for SEKAIHOME; Ollama on the tunnel address only | M | A2 |
| A6 | Deferred queue (section 4.1) | L | S2, S3 |
| S7 | Identity inside the main VM | L | A1 |
| A7 | Installer `scripts/gcp-install.sh`, run from the admin's own machine (gcloud + Terraform) so key material never passes through Google-hosted shells; `destroy`, `restore <date>` | M | A1-A6, S7 |
| A8 | Tests on a staging project (section 6) | M | all |
| R | Remove redundant parts (shared file section 5) | S | S2 |
| A9 | User guide (privacy boundary, what alerts mean, queue, external consent) and admin runbook (unlock, keys, attestation failures) | S | A8 |

Order: A0 -> A-S0 -> S1, S1b, S8 -> S2, S3, S6, A1 -> R -> S4, S5 -> A2 -> A3 -> A4, A5 -> A6 -> S7 -> A7 -> A8 -> A9.

## 6. Acceptance tests

1. With `external.enabled: false`, the leak canary mock receives nothing on any route.
2. With external enabled: no sensitive request, nothing without consent or grant, nothing while the gate is down,
   nothing via fallback, and no user identifiers reach the mock.
3. A request with the model server stopped: it starts, attestation passes, the disk unlocks, the answer arrives, and
   the server stops after the idle time.
4. Tampered boot (a measurement mismatch): the broker refuses the key; the disk stays locked; the request goes to
   `onprem` or the queue; the admin is alerted.
5. A disk snapshot and a backup object taken through Google's APIs are unreadable without the broker's key.
6. Cloud Logging and the serial console hold no prompt, answer or file name.
7. Every private host down: "queued" reply within 3 s; answer delivered after a host returns, with an email.
8. A photo with a face is processed by a private vision model; never queued to an external route.
9. Cross-user: user B cannot see user A's chats, queue items or consents.
10. Restore drill under 1 hour, including broker unlock.

## 7. Cost (rough, unverified; confirm in the pricing calculator during A-S0)

| Item | Month |
|---|---|
| Main VM: N2D Confidential VM (2 vCPU, 8 GB), disk, static IP, backups | ~$65-80 |
| `confidential-cpu` model server | ~$0.4-1 per hour while running; $0 stopped (disk ~$5) |
| `confidential-gpu` (optional) | ~$10+ per hour while running |
| `onprem` | $0 |
| External APIs (optional) | per token |
| **Idle floor** | **~$70-85** |

Confidential computing roughly doubles the earlier non-confidential floor (~$30), because the smallest
confidential-capable machine types are larger than e2.

## 8. Decisions

| # | Decision | Default |
|---|---|---|
| A-D1 | Private host order | `confidential-cpu`, then `onprem` |
| A-D2 | GPU confidential server | off |
| A-D3 | Where the key broker runs | SEKAIHOME (owned hardware); manual unlock if it is offline at a reboot |
| A-D4 | External models | disabled; if enabled, which providers and which groups |
| A-D5 | Special categories on confidential cloud hosts | allowed (`special_categories_location: any`) |
| A-D6 | Region (must offer the chosen confidential machine types) | from A-S0 |
| A-D7 | Domain, DNS provider, SMTP relay | required |
| A-D8 | Model server idle stop | 20 minutes |

## 9. Risks

| Risk | Mitigation |
|---|---|
| CPU inference too slow for daily use | A-S0 measures first; on-prem second in the order; GPU option for heavy windows |
| Confidential VMs do not live-migrate; host maintenance reboots them and needs an unlock | broker unlocks automatically after attestation; manual unlock runbook; maintenance notifications |
| Broker offline at reboot | admin unlock; second broker copy on the admin's machine |
| Hardware or firmware vulnerability in confidential computing | firmware and image updates; attestation pins measurements; special categories can be kept on-prem (A-D5) |
| Gate false negatives once external is enabled | external stays off by default; consent per conversation; S8 recall gate; audit review |
| Cost of confidential machines | idle stop for the model server; the main VM is the only always-on machine |
