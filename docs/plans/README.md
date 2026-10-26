# Implementation plans (2026-10-26)

Two ways to run the stack for several people with Open WebUI as the only front end. Both share one privacy gate:
sensitive requests (personal data, secrets, sensitive topics) never reach an external model API.

| | [Plan A: cloud-led](PLAN-A-CLOUD-LED.md) | [Plan B: local-led](PLAN-B-LOCAL-LED.md) |
|---|---|---|
| Main processor | small Google Cloud VM | local GPU server (SEKAIHOME) |
| Non-sensitive work | external APIs at every tier | local for simple/medium, external API for complex/reasoning |
| Sensitive work | private host: on-prem over WireGuard and/or a private Cloud Run GPU | local, at every tier |
| No private host available | queued, answered later, user notified | not applicable (the local server is the private host) |
| Where chats are stored | the cloud VM (our project) | the local server; the edge VM sees no chat content |
| Works when the home PC is off | yes, except sensitive requests are queued if the cloud GPU is also off | no (offline page) |
| Idle cloud cost (rough) | ~$30 a month | $0-5 a month |
| Biggest risk | the gate's false negatives send data to an API | sensitive complex work gets weaker local answers |

Shared work for both: [SHARED-COMPONENTS.md](SHARED-COMPONENTS.md) (privacy gate, LiteLLM enforcement hook, Open
WebUI integration, build changes, identity edge, multi-user orchestrator, evaluation and leak canary).
Identity and security behaviour: [../GCP-DESIGN.md](../GCP-DESIGN.md) section 4 onwards.

Plan B reuses most of what already runs and can start in `owner` mode once S1-S4 and B1-B2 are done, so it is the
shorter path. Plan A adds the cloud VM, the deferred queue and a private cloud GPU on top of the same shared work.
Because S1-S7 are common, building B first and A later wastes little.
