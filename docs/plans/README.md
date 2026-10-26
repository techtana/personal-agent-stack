# Implementation plans (2026-10-26, private first)

The project is private first. Every request is processed by private models: on hardware we own, or on confidential
cloud VMs that the cloud provider cannot read. External model APIs (Anthropic, Vertex AI, Hugging Face and others) are
off at install; when an admin enables them they are a deliberate, last-resort user choice, and a local privacy gate
refuses anything sensitive with no override. Open WebUI is the user surface. No add-ons are offered for clients that
talk to their own cloud (Claude Code on a subscription, Claude Desktop), because there they could only advise.

| | [Plan A: cloud-led](PLAN-A-CLOUD-LED.md) | [Plan B: local-led](PLAN-B-LOCAL-LED.md) |
|---|---|---|
| Main processor | Confidential VM in our Google Cloud project (TLS, data and keys inside it) | SEKAIHOME (native services, no Docker) |
| Private models | confidential model server (CPU, optional GPU) started on demand, then on-prem; queue when neither is up | local GPU, every tier |
| Provider access to data | memory encrypted in use (SEV-SNP / TDX), checked by attestation; disks and backups encrypted with keys held outside Google | none; the edge relay sees only encrypted traffic |
| External models | optional, off by default, explicit and consented, non-sensitive only | same |
| Works when SEKAIHOME is off | yes (confidential model server; the key broker must be reachable at reboots or the admin unlocks) | no |
| Idle cloud cost (rough) | ~$70-85 a month | $0-5 a month |
| Biggest risk | CPU inference speed on the confidential server; trust in CPU vendors' confidential computing | weaker local answers for complex work |

- [SHARED-COMPONENTS.md](SHARED-COMPONENTS.md): principles and the privacy boundary, data classes and private tiers,
  the external access policy, the privacy gate (text, profiling, media), the LiteLLM enforcement hook, Open WebUI
  integration, the MCP server, build changes, identity (TOTP, passkeys, invites with approval), evaluation with a leak
  canary, and the redundant parts to remove.
- [INSTALL.md](INSTALL.md): dependencies per platform and every configuration step; the optional Harbor runtime.

Both plans start with the gate and its evaluation set. Plan B reaches a usable `owner` mode sooner.
