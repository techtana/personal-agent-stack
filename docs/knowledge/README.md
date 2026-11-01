# Knowledge base

What a newcomer needs to understand about the subjects this stack is built on. These files explain the domain:
what the ideas are, the numbers that matter, what we measured, and where to read more. They do not repeat setup
steps ([manuals](../manuals/)), choices and their reasons ([design/DECISIONS.md](../design/DECISIONS.md)) or the raw
research notes ([research/](../research/README.md)); they link to them.

Files are kept current: when understanding improves, the explanation is rewritten and a dated line is added under
**Changes** at the bottom of the file.

## Reading order

**Start here**

1. [local-llm-inference.md](local-llm-inference.md): how a model runs on one consumer GPU: weights, quantization,
   VRAM versus RAM, the KV cache, prefill and decode speed, mixture-of-experts offload, Ollama settings. For anyone
   who changes `machines/*.yaml` or wonders why the 9B beat the 35B here.
2. [llm-gateway-and-routing.md](llm-gateway-and-routing.md): how clients talk to models through LiteLLM: the
   OpenAI and Anthropic formats, tool calls, aliases, routers, retries, hooks, and Claude Code on a gateway. For
   anyone who touches `infrastructure/litellm/` or `scripts/stacklib/litellm_build.py`.

**Foundations for the private-first plans**

3. [privacy-for-llm-systems.md](privacy-for-llm-systems.md): the privacy boundary, why advice is not enforcement,
   detecting personal data, secrets and sensitive media, consent, measuring a detector, and identity basics. For
   anyone working on the privacy gate (S1-S8) or reviewing a plan.
4. [confidential-computing.md](confidential-computing.md): how a cloud VM can process data its provider cannot read:
   SEV-SNP, TDX, attestation, key brokers, and what the provider still sees. For Plan A.

**Running it on Windows**

5. [windows-service-hosting.md](windows-service-hosting.md): processes, consoles, job objects, Smart App Control,
   pid files, the tray app and Task Scheduler. For anyone debugging a service that will not start or stay up.
6. [agent-file-isolation.md](agent-file-isolation.md): accounts, NTFS permissions and why an agent's own settings
   cannot keep it out of personal files. For the isolation plan.

**Agents and how the stack improves**

7. [coding-agents-and-self-improvement.md](coding-agents-and-self-improvement.md): agent loops, subagents,
   instruction and memory files, skills, MCP, and the human-gated retro and eval loop. For anyone editing `agents/`,
   skills or the retro.
8. [llm-observability-and-cost.md](llm-observability-and-cost.md): tokens, prices, latency, traces and spans, what
   to log and what not to, and the tray's usage figures. For anyone reading the Usage tab or changing tracing.

**Elsewhere in the repo**

- UX: the `/ux-rules` skill carries its own researched catalog of 122 UX rules with evidence grades and sources, in
  [.claude/skills/ux-rules/references/](../../.claude/skills/ux-rules/references/README.md).
- Raw research and critiques from 2026-10-24: [research/README.md](../research/README.md).
- Anthropic API facts used by the gateway: [research/anthropic-facts-2026-10.md](../research/anthropic-facts-2026-10.md).

## Glossary

| Term | Meaning |
|---|---|
| Agent loop | A model that calls tools, reads the results and decides the next step until the task is done. |
| Alias | A model name the gateway exposes (for example `local-primary`) that maps to one or more real deployments. |
| Attestation | A signed report from the CPU that says what software a confidential VM booted, checked before it gets keys. |
| Confidential VM | A virtual machine whose memory is encrypted by the CPU, so the host and cloud provider cannot read it. |
| Context length (`num_ctx`) | How many tokens a model can consider at once: prompt plus answer. Costs memory through the KV cache. |
| Data class | The label on a deployment saying whether data sent there stays private (`private`) or leaves (`external`). |
| Decode | Generating the answer one token at a time; usually limited by memory bandwidth. |
| Deployment | One concrete model behind the gateway (a provider, a model name and its options). |
| Department | One of the six agent roles (`app-dev`, `testing`, `security`, `devops`, `code-review`, `docs`), defined in `agents/*.yaml`. |
| Embedding | A list of numbers that represents the meaning of a text, used for search and similarity. |
| Eval gate | A set of tests a prompt or routing change must not get worse on before it is merged. |
| GGUF | The file format llama.cpp and Ollama use to store a model's weights and metadata. |
| Job object | A Windows group of processes; with kill on close, all of them end when the job closes. |
| KV cache | Memory that holds what the model has already read, so it does not reread the whole context for each token. |
| MCP | Model Context Protocol: a standard way for an agent to call tools provided by a separate server. |
| MoE (mixture of experts) | A model that uses only a few of its many sub-networks (experts) for each token, so active size is far below total size. |
| mmap | Mapping a file into memory so the operating system loads pages on demand instead of copying the whole file. |
| NTFS ACL / ACE | The permission list on a file or folder (ACL) and one entry in it (ACE), which allows or denies an account. |
| Pid | Process id: the number Windows gives a running process. Windows reuses them. |
| Prefill | Reading the prompt before the first answer token; fast because it processes many tokens at once. |
| Privacy boundary | The line inside which data may be processed; only private deployments are inside it. |
| Privacy gate | The planned local service that classifies requests and refuses sensitive data before it can leave. Not built yet. |
| Profile A / profile B | Claude Code on the owner's subscription (A) or pointed at the local gateway (B). |
| Quantization | Storing weights with fewer bits (for example about 4 instead of 16) so a model fits in less memory. |
| Recall / precision | Of all sensitive items, the share the detector caught (recall); of all items it flagged, the share that were sensitive (precision). |
| Router (complexity router) | Gateway logic that picks a tier for each request; here a fast heuristic, no model call. |
| Skill | A folder with a `SKILL.md` that gives an agent instructions and resources for one kind of task. |
| Smart App Control | A Windows feature that blocks unsigned or unknown programs and modules by reputation. |
| Span / trace | One timed step of a request (span) and the record of a whole request (trace). |
| Tier | A level of model capability in a department's router (for example `local-small`, `local-primary`). |
| Token | A small piece of text a model reads or writes; prices and speeds are counted in tokens. |
| Tool call | A structured request from the model to run a function, whose result is sent back for the next turn. |
| VRAM | The GPU's own memory; fast, but small (12 GB on SEKAIHOME). |

## Changes

- 2026-11-01: first version: eight topic files, reading order and glossary.
