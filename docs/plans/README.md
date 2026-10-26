# Implementation plans (2026-10-26, revised)

Two ways to run the stack for several people, with Open WebUI as the main front end, Harbor as the installer and
runtime, and one local privacy gate. Sensitive requests never reach an external model API: personal, special-category
and profilable information, secrets, and images, video or audio showing people.

| | [Plan A: cloud-led](PLAN-A-CLOUD-LED.md) | [Plan B: local-led](PLAN-B-LOCAL-LED.md) |
|---|---|---|
| Main processor | small Google Cloud VM (Harbor on Linux) | SEKAIHOME (Harbor in WSL2, native Ollama) |
| Non-sensitive work | external APIs at every tier | local for simple/medium, external API for complex/reasoning |
| Sensitive work | private host: on-prem over WireGuard and/or a private Cloud Run GPU | local, at every tier |
| No private host available | queued, answered later, user notified | not applicable |
| Where chats are stored | the cloud VM (our project) | SEKAIHOME; the edge VM sees no chat content |
| Works when SEKAIHOME is off | yes; sensitive requests queue unless the cloud GPU is configured | no (offline page) |
| Idle cloud cost (rough) | ~$30 a month | $0-5 a month |
| Biggest risk | gate false negatives send data to an API | weaker local answers for sensitive complex work; WSL RAM |

- [SHARED-COMPONENTS.md](SHARED-COMPONENTS.md): privacy gate (text and media), redaction, LiteLLM enforcement hook,
  Open WebUI integration, MCP server and skill for other apps, build changes, identity edge, evaluation with a leak
  canary, and the list of redundant parts to remove (orchestrator, native service manager and tray, Phoenix, uv tool
  installs).
- [INSTALL.md](INSTALL.md): dependencies per platform and every configuration step, the manual path that
  `stack.py install` automates.
- Identity and security behaviour: [../GCP-DESIGN.md](../GCP-DESIGN.md) section 4 onwards.

Both plans start with H0 (a half-day Harbor spike) and the gate with its evaluation set. Plan B reaches a usable
`owner` mode sooner; Plan A adds the cloud VM, the deferred queue and a private cloud GPU on the same shared work.
