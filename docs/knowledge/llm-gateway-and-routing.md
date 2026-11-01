# LLM gateways and request routing

How chat clients talk to models, what a gateway adds, and how the stack decides which model answers.

## What this is and why the project needs it

A language model runs as a program that waits for text and sends text back. Many different programs want to use it:
Claude Code, Open WebUI, OpenCode, test tools and the orchestrator. Each one speaks a slightly different dialect, and
each one needs the right model, the right settings and a record of what happened. A gateway is one door in front of all
the models. Clients knock on that door with a model name, and the gateway picks the real model, adds logging, retries
failures and refuses requests that break a rule. This project uses a gateway (LiteLLM) so that every request stays on
the owner's own machine, so that one tool can change models without touching the others, and so that the retrospective
can read what was routed where.

## The ideas, built up from zero

### 1. A model is a service you call over HTTP

Think of a receptionist at a front desk. You hand over a written request, and a written answer comes back. A model API
works the same way. A client sends an HTTP request (a text message over the network) to an address, such as
`http://127.0.0.1:11434` for Ollama on this machine. The request body is JSON: structured text with fields. The
response is JSON too. HTTP gives each response a status code. 2xx means success. 4xx means "your request is wrong, do
not repeat it unchanged". 5xx means "something broke on my side, trying again might work". Section 4 below shows why
that split matters.

The analogy stops at memory. A receptionist remembers the conversation. A model API remembers nothing. The client
resends the whole conversation every time.

### 2. Messages, roles and system prompts

A conversation is a list of messages. Each message has a role:

- `system`: standing instructions ("you are a code reviewer"). The model treats them as the ground rules.
- `user`: what the person asked.
- `assistant`: what the model said earlier.
- `tool`: the output of a tool the model asked for (see below).

The client sends the list so far, and the model writes the next assistant message. A model has a context window: the
maximum amount of text (counted in tokens, roughly word pieces) it can read in one request. The request and the answer
must fit inside it. Ollama calls the setting `num_ctx`.

### 3. Two dialects: OpenAI chat completions and Anthropic Messages

Two request formats matter here. Both carry the same ideas in different shapes.

OpenAI chat completions, sent to `POST /v1/chat/completions`. The system prompt is a message with role `system`:

```json
{
  "model": "docs",
  "messages": [
    {"role": "system", "content": "You write short, plain documentation."},
    {"role": "user", "content": "Explain what a gateway is in one sentence."}
  ],
  "max_tokens": 200
}
```

Answer shape: `choices[0].message.content` holds the text, and `usage` counts tokens.

Anthropic Messages, sent to `POST /v1/messages`. The system prompt is a separate top-level field, `max_tokens` is
required, and content is a list of typed blocks (`text`, `tool_use`, `tool_result`, `thinking`):

```json
{
  "model": "docs",
  "system": "You write short, plain documentation.",
  "messages": [
    {"role": "user", "content": "Explain what a gateway is in one sentence."}
  ],
  "max_tokens": 200
}
```

Answer shape: a `content` list of blocks, plus `stop_reason`. In this stack Claude Code reaches the gateway through the Anthropic endpoint (profile B). Open WebUI,
OpenCode and promptfoo speak the OpenAI one. A gateway that understands both lets all of them share the same models.
(Source: `docs/ORCHESTRATOR-DESIGN.md` section 4 lists which surface uses which endpoint.)

### 4. Streaming

A model writes one token at a time. Without streaming, the client waits for the full answer. With streaming, the server
sends the answer in small pieces as they appear, using server-sent events (SSE): a long-lived HTTP response that
delivers lines such as `data: {...}`. Chat UIs stream so that text appears at once. A gateway must pass these pieces
through as they come. If it collects them first, the user sees nothing until the end, and Claude Code's own research
notes say a gateway has to stream event by event and forward the keep-alive pings.

### 5. Tool (function) calling and the round trip

A model cannot run code or read a file. It can only write text. Tool calling gives it a structured way to ask. The
client lists the tools it offers (name, description, a JSON schema for the arguments). If the model decides a tool
would help, it answers with a tool call instead of prose. The client runs the tool itself and sends the result back as
a new message. The model then continues. This round trip repeats until the model answers in plain text.

Round trip, OpenAI shape (written for this document, no real data):

```json
// 1. Client -> model: offers one tool
{"model": "app-dev", "messages": [{"role": "user", "content": "What is in README.md?"}],
 "tools": [{"type": "function", "function": {"name": "read_file",
   "description": "Read a file", "parameters": {"type": "object",
   "properties": {"path": {"type": "string"}}, "required": ["path"]}}}]}

// 2. Model -> client: asks for the tool (no prose, finish_reason is "tool_calls")
{"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": null,
  "tool_calls": [{"id": "call_1", "type": "function",
    "function": {"name": "read_file", "arguments": "{\"path\": \"README.md\"}"}}]}}]}

// 3. Client runs read_file, then sends the history again plus the result
{"model": "app-dev", "messages": [
  {"role": "user", "content": "What is in README.md?"},
  {"role": "assistant", "content": null, "tool_calls": [{"id": "call_1", "type": "function",
    "function": {"name": "read_file", "arguments": "{\"path\": \"README.md\"}"}}]},
  {"role": "tool", "tool_call_id": "call_1", "content": "# Project\nA small agent stack."}
], "tools": ["...same list..."]}
```

In the Anthropic shape, step 2 is a `tool_use` block inside the assistant message, and step 3 is a user message that
holds a `tool_result` block with the matching `tool_use_id`.

The model never runs the tool. The client does. That is why a tool call is a request, not an action, and why the client
decides which tools are allowed.

### 6. Why a hand-rolled proxy broke tool-using clients

The first router in this repo was a small FastAPI program (`router/main.py`). It scored the prompt with keywords and an
800-token length check and spoke only the OpenAI dialect. Its request model silently dropped `tools`, so a client got a
plain-text 200 answer with no `tool_calls` (source: `docs/research/critique-router-code.json`). Tool-using clients need every
detail of the round trip to survive: the `tools` list, `tool_calls` in the answer, matching ids, `finish_reason`, and
the same pieces in streaming mode. A proxy that drops or rewrites any of them breaks the loop with no obvious error.
Claude Code could not use it at all, because the router had no `/v1/messages` endpoint. The project's lesson from 2026-10-24: do not
write the proxy by hand; use LiteLLM. (Sources: `memory/lessons.md` 2026-10-24; routing research summary in
`docs/research/README.md`.)

### 7. Embeddings

An embedding model turns text into a list of numbers (a vector) so that texts with similar meaning land near each
other. It does not write replies. Uses: search, retrieval of notes, and semantic routing. Clients call
`POST /v1/embeddings`. In this stack the embedding model is `nomic-embed-text`, served through the alias `local-embed`.

A related call is fill-in-the-middle (FIM) completion for editor autocomplete. The model sees the text before and
after the cursor and writes what goes between. The alias `local-fim` serves that, using a small base model.

### 8. What a gateway adds

```
  Claude Code ──/v1/messages──┐
  Open WebUI ──/v1/chat/...───┤        ┌────────────┐      ┌──────────────────┐
  OpenCode, promptfoo ────────┼──────► │  gateway   │ ───► │ deployment: Ollama│
  orchestrator MCP server ────┘        │  (LiteLLM) │      │  qwen3.5:9b, etc. │
                                       │ auth, alias│ ───► │ deployment: cloud │ (off here)
                                       │ route, log │      └──────────────────┘
                                       └────────────┘
```

A gateway gives the owner:

- One endpoint and one key for all clients.
- Aliases: a stable name such as `docs` that can point to different real models over time.
- Format translation: Anthropic dialect in, Ollama's native API out.
- Retries and fallbacks when a deployment fails or a prompt is too long.
- Logging and cost tracking in one place.
- A place to enforce rules (privacy checks, who may use which model).

The analogy to a switchboard holds for aliases and routing. It stops at policy: a switchboard operator connects calls,
while a gateway can also read, change, log and refuse them.

### 9. LiteLLM vocabulary

LiteLLM is an open-source gateway written in Python. The terms below appear in `infrastructure/litellm/config.yaml`,
which is generated, so edit the sources and run `uv run scripts/stack.py build` (rule 1 in `AGENTS.md`).

- **model_list**: the list of model entries. Each has a `model_name` (the alias a client asks for) and
  `litellm_params` (what to call: provider and model, `api_base`, options like `num_ctx` and `keep_alive`).
- **Deployment**: one real backend behind an alias. Several deployments can share one `model_name`; LiteLLM then
  shares load between them (`routing_strategy: simple-shuffle`).
- **Alias**: the `model_name`. A client never needs to know the real model.
- **model_info**: extra facts about the entry (token limits, cost per token, `supports_function_calling`). This
  project also stores `data_class` and `location` here for the privacy check.
- **router_settings**: how the internal router behaves: `num_retries`, `allowed_fails`, `cooldown_time` (how long a
  failing deployment sits out), and fallbacks.
- **litellm_settings**: global switches: `callbacks`, `request_timeout`, `drop_params`.
- **general_settings**: gateway-level items such as `master_key`, the admin key every client uses here.
- **Fallbacks**: a list that says "if model A fails, try model B". `context_window_fallbacks` apply only when the prompt
  is too long for A. `default_fallbacks` apply to any alias without its own entry.
- **drop_params**: when true, LiteLLM removes request fields a provider does not accept instead of failing. The project
  relies on this to strip sampling settings for Anthropic models.

### 10. Provider prefixes: `ollama_chat/` versus `ollama/`

The prefix on a LiteLLM model string picks the code path. `ollama_chat/<model>` calls Ollama's `/api/chat`, which
accepts `tools` and `num_ctx`. `ollama/<model>` calls `/api/generate`, a plain text-completion path that does not
accept `tools`. Chat and tool use need `ollama_chat/`. FIM and embeddings use `ollama/`, because they are not chat.
The generated config follows this: `local-fim` and `local-embed` use `ollama/`; `local-small`, `local-primary` and
`<dept>-local` use `ollama_chat/`. (Source: routing research, checked in LiteLLM source at v1.108.0, commit 5603724,
2026-10-24.)

### 11. Retries: why 4xx and 5xx behave differently

When a deployment returns an error, the router decides whether to try again. A 5xx says "temporary failure", so the
router retries and may switch to a fallback. A 4xx says "the request itself is wrong", so repeating it cannot help. Now
suppose a guard hook wants to refuse a request because it breaks the privacy rule. If the hook raises a plain Python
exception, the proxy turns that into a 500. The router sees a 5xx, retries three times, and may even answer from a
fallback, which defeats the refusal. A refusal must therefore raise an error with a 4xx status code that the router
treats as non-retryable. (Source: `docs/plans/SHARED-COMPONENTS.md` section 7, V1; `memory/lessons.md` 2026-10-26.)

### 12. Callbacks and hooks

LiteLLM lets you attach a Python class (a `CustomLogger` subclass) to the proxy. Its methods run at fixed points:

- `async_pre_call_hook`: before routing. It can change the request, reject it (return a string), or raise.
  Research found it can rewrite `data["model"]`.
- `async_pre_call_deployment_hook`: after the router has chosen the real deployment, before the provider call. It sees
  the chosen deployment in `kwargs["model_info"]`. V1 confirmed this on both `/v1/chat/completions` and `/v1/messages`.
- `async_log_success_event` and `async_log_failure_event`: after the call, for logging.
- `async_post_call_success_hook` and `async_post_call_streaming_iterator_hook`: change the response on its way out.

The project's `infrastructure/litellm/custom_callbacks.py` uses the logging hooks to write one JSON line per request to
`traces/litellm/YYYY-MM-DD.jsonl`, and the post-call hooks to append a "Used / Route" footer to routed chat replies
for Open WebUI. It stores no prompt or reply text.

### 13. Authentication, users and virtual keys

By default the gateway checks one `master_key`. Anyone holding it can use any alias. To tell users apart, LiteLLM
offers three ways, and only some work without a database:

- **Virtual keys**: the gateway issues keys with budgets and model limits. They need Postgres (`DATABASE_URL`) because
  the keys and spend live in a database. The admin UI at `/ui` also reads that database, which is why it shows "Not
  connected to DB!" on this machine (`memory/state.md`, open item 9).
- **`user_header_name`**: names a request header (Open WebUI can forward the user's email) that LiteLLM stores as the
  end-user id. Limits attached to that end user live in the database. Without Postgres the lookup fails, is logged only
  at debug level, and the request goes through with no limit. That is "failing open".
- **`custom_auth`**: your own Python function runs on each request and returns who the caller is and which models
  they may use. With `litellm_settings.enable_post_custom_auth_checks: true`, LiteLLM enforces that model list on
  every request. Without the flag it only filters the `/v1/models` listing. Tested result: 403
  `key_model_access_denied`. JWT auth is enterprise-only.

(Source: V2 in `docs/plans/SHARED-COMPONENTS.md` section 7; `memory/lessons.md` 2026-10-26.)

### 14. Pointing Claude Code at a gateway

Claude Code normally talks to Anthropic. Setting `ANTHROPIC_BASE_URL` sends it to another address. Claude Code then
treats that address as an Anthropic endpoint and sends its full feature set: adaptive thinking and cache markers, and, for
model names it does not recognise, `output_config.effort` and system entries inside `messages`. The gateway must accept or ignore those fields.

Billing follows the credential. If the process has `ANTHROPIC_AUTH_TOKEN` (or an API key or key helper), requests no
longer use the Max subscription. The credential is billed per token. Only a credential-less pass-through that forwards
the subscription's OAuth header keeps subscription billing, and Anthropic's terms limit OAuth to ordinary personal use
(research, high confidence; not tested here).

The project keeps two profiles:

- **Profile A**: Claude Code talks to Anthropic directly on the subscription. Departments are subagents with
  `model: haiku|sonnet|opus`.
- **Profile B**: `scripts/claude-local.ps1|.sh` sets `ANTHROPIC_BASE_URL` to the local gateway, `ANTHROPIC_AUTH_TOKEN`
  to the gateway key, `ANTHROPIC_MODEL=local-primary`, sets the max-context variable to the local `num_ctx` (32768), max output to 8192 and the
  auto-compact window to at least 100000. It also
  sets `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` and `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`.

A Claude Code process has exactly one base URL, so it cannot send one subagent to Ollama and another to Anthropic
without a gateway that maps model names. Ollama also exposes its own `/v1/messages` (since v0.14.0), so Claude Code can
talk to Ollama directly, but that skips the gateway's logging and rules.

### 15. Anthropic API constraints that a gateway must respect

From `docs/research/anthropic-facts-2026-10.md` (cached 2026-10-06, verified in-session 2026-10-24):

- Since 2026-10-21, `temperature`, `top_p` and `top_k` return HTTP 400 on every Claude model. Local models may still
  take them.
- A forced `tool_choice` of `any` or `tool` returns 400 on the 5.x models listed there. Use `auto`.
- Assistant prefill returns 400 on all current models.
- `output_config.effort` (`low` to `max`) is the main cost lever within a model.

None of this affects the current build, because external models are off. It matters when a cloud alias is added.

### 16. MCP as a separate channel

The Model Context Protocol (MCP) lets a client call tools hosted in another process. It does not carry the model
conversation. The model's own request still goes to the gateway. MCP is a side channel for tools. In this repo the
orchestrator MCP server (`.mcp.json`, port 8765) offers five tools: `list_departments`, `delegate`, `get_job`,
`cancel_job` and `record_lesson`. See
`docs/ORCHESTRATOR-DESIGN.md` section 4 for how it sits next to the gateway; this document does not cover it further.

### 17. Routing patterns

Routing means choosing a model for each request. Four patterns, from simple to complex:

1. **Static alias.** The client asks for `local-primary`; it gets `local-primary`. No decision. Predictable, cheap.
2. **Heuristic (complexity) routing.** The gateway scores the request with rules (length, keywords, code markers,
   reasoning words) and maps the score to a tier, for example SIMPLE, MEDIUM, COMPLEX, REASONING. Each tier names a
   model. It runs in under a millisecond, offline, and the same input always gives the same answer.
3. **Semantic routing.** The gateway embeds the request and compares it with example sentences for each route ("this
   looks like a billing question"). It picks the nearest route. It classifies intent, not difficulty, and needs an
   embedding call.
4. **Learned routers.** A model trained on preference data (RouteLLM is the example) predicts whether a cheap model
   will do. They can beat rules, but they need training data, often an external embedding service, and upkeep.
   LiteLLM's `adaptive_router` is a related idea: it learns from feedback (Thompson sampling) and needs Postgres.

The project chose pattern 2. Reasons recorded in the research: RouteLLM looked dormant (no releases listed) and its
`mf` and `sw_ranking` routers needed an OpenAI key for embeddings, which breaks the private-first rule; semantic-router
sorts by intent, not difficulty, and LiteLLM already wraps it; a model-based router such as Arch/Plano (a 4B classifier) is
heavy next to coder models on 12 GB, while the heuristic takes under 1 ms with no model call. The design treats the heuristic as the starting point. The retrospective (`stack.py retro`) proposes
changes to tier boundaries from evidence, and `adaptive_router` is the upgrade once there is traffic and Postgres.

## Rules of thumb and typical numbers

| Rule or number | Source |
|---|---|
| Use `ollama_chat/` for anything with tools; `ollama/` does not accept `tools` | `docs/research/research-routing-proxy.json`, LiteLLM source at v1.108.0 |
| Heuristic complexity classification takes under 1 ms and needs no network | same file; `docs/ORCHESTRATOR-DESIGN.md` section 7 |
| Router settings in use: `num_retries: 1`, `allowed_fails: 2`, `cooldown_time: 30`, `request_timeout: 600` | generated `infrastructure/litellm/config.yaml` |
| Complexity router stall escalation: window 6, repeat threshold 2; context escalation buffer 0.9 | `scripts/stacklib/litellm_build.py` |
| A raised plain exception becomes HTTP 500 and is retried three times; raise a 4xx | `docs/plans/SHARED-COMPONENTS.md` V1 |
| Two tiers sharing one Ollama model should share `num_ctx` and load options, or Ollama reloads the model on each switch | `memory/lessons.md` 2026-10-25 |
| Ollama recommends a 64k or larger context for Claude Code; this stack runs 32k | Ollama doc cited in research; `memory/state.md` |
| Ollama's `/v1/messages` lacks `tool_choice`, `count_tokens` and prompt caching | research-claude-code-local.json |
| Virtual keys, budgets, spend tracking and the admin UI need Postgres; callbacks and caching do not | research-routing-proxy.json; V2 |
| A gateway must stream without buffering and return `retry-after` as whole seconds | code.claude.com gateway protocol page, via the research file |
| Set a local Claude Code profile's max-context variable to the model's `num_ctx` | `scripts/stacklib/claude_env.py` |

## Common misconceptions and edge cases

- **"The gateway remembers the chat."** It does not. Each request carries the full history. Memory lives in the client.
- **"A system prompt is part of the gateway."** Not here. The gateway does not inject system prompts. Claude Code
  carries them in `.claude/agents/*.md`, Open WebUI and the orchestrator send them per request, and promptfoo keeps them
  in `prompt.json` (`docs/ORCHESTRATOR-DESIGN.md` section 7).
- **"An OpenAI-compatible server works with every client."** It works with clients that speak that dialect and only
  for the features it implements. Tool calls and streaming are where partial compatibility shows up first.
- **"The model ran my tool."** The client ran it. The model only asked.
- **"A guard that throws an error refuses the request."** A plain exception becomes a 500 and the router retries it,
  possibly through a fallback. Only a 4xx stops it.
- **"Setting `user_header_name` limits users."** Without Postgres it limits nobody, and it only logs at debug level.
  The default is silent failure.
- **"A model-level guardrail scope exists in the docs."** Not found: guardrails were global, per key or per request.
  A `guardrails:` list under a deployment's `litellm_params` does scope per model (V1 test), so check the version.
- **"Pass-through routes go through my hooks."** They skip them. Do not configure pass-through endpoints and test that
  `/anthropic/*` and `/vertex_ai/*` return 404 (S3 plan).
- **"Aliases protect against a bad fallback."** A fallback can name any deployment. The project's build fails if any
  tier, fallback or default points to a non-private deployment, because a tier name alone proves nothing.
- **"Claude Code's setting survives a gateway."** Some fields (adaptive thinking, `effort`, `role: system` inside
  `messages`) can cause 400 errors on local backends. Claude Code retries once without the rejected piece, and each
  retry costs time. `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` removes most pre-release fields but not those three
  (research, high confidence).
- **"Setting `ANTHROPIC_BASE_URL` alone is safe for subscription billing."** With only the base URL, the login stays
  active, but the gateway must forward the OAuth beta header. With any credential variable, billing moves to per-token.
- **Two names for one thing.** The two Haiku IDs in the research notes (`claude-haiku-4-5-20251001` and
  `claude-haiku-5-5`) conflicted. The Anthropic facts file lists `claude-haiku-5-5`. Disputed; the research said to
  confirm through the models listing with the owner's key. No cloud key exists on this machine, so it is unchecked.

## How the project uses it

- **Aliases.** Each department (`app-dev`, `testing`, `security`, `devops`, `code-review`, `docs`) has two aliases:
  `<dept>` is a complexity-router entry that maps SIMPLE, MEDIUM, COMPLEX and REASONING to local aliases;
  `<dept>-local` is a direct `ollama_chat/` deployment of the primary model, with the same `num_ctx` and load options
  as `local-primary` so Ollama keeps one runner loaded.
- **Base aliases.** `local-fim` (FIM, `qwen2.5-coder:1.5b-base`), `local-embed` (`nomic-embed-text`), `local-small` and
  `local-primary` (both `qwen3.5:9b` at `num_ctx` 32768 on SEKAIHOME), `local-reviewer` (`flint:40b-a2b`, not pulled, no
  tier routes to it). A model a machine lacks falls back to the best local one when the config is built.
- **Router config.** Every department router uses `classifier_type: heuristic`, escalation keywords `ESCALATE` and
  `use claude`, stall and context-window escalation, and optional `plan_mode_min_tier` and `keyword_tier_rules` from the
  department's YAML. On this machine all tiers resolve to `local-primary`, so routing exists in the config but has one
  destination today. `context_window_fallbacks` sends `local-small` overflow to `local-primary`.
- **Private-only build.** `scripts/stacklib/litellm_build.py` refuses to build when `policy/privacy.yaml` has
  `external.enabled: true`, tags each deployment with `data_class` and `location`, and `check_private()` stops the
  build if a tier, default, fallback or profile B alias names a non-private deployment.
- **Trace callback.** `custom_callbacks.proxy_handler_instance` writes JSONL traces: requested alias, served model,
  provider, routing decision, tokens, cost, latency, Claude Code hint headers and Ollama load, prefill and decode
  times. `otel` sends spans to Phoenix when enabled; Phoenix is broken on
  SEKAIHOME and slated for removal, so today the callback has no collector. `stack.py why-routed` reads the traces.
- **Profile B.** `scripts/claude-local.ps1|.sh` runs Claude Code on the gateway with private aliases only and denies the
  `WebFetch` and `WebSearch` tools in its own settings (the reason is not recorded; both tools reach the web directly).
- **Planned enforcement.** `docs/plans/SHARED-COMPONENTS.md` S3 describes a `custom_auth` function plus
  `enable_post_custom_auth_checks` for per-user model access, and a final deployment-level guardrail that raises a
  non-retryable 4xx. Not built yet.
- **Why these choices.** See [the decision record](../design/DECISIONS.md).

## What we found

- **2026-10-24, the hand-written proxy.** The first router broke tool-using clients and could not serve
  `/v1/messages`. The project switched to LiteLLM (`memory/lessons.md`).
- **2026-10-24, research on LiteLLM.** In the source at v1.108.0 (commit 5603724), `ollama_chat/` supports tools; the
  proxy bridges `/v1/messages` to non-Anthropic deployments with tools preserved; the complexity router exists as a
  deployment type. The deployed version here is 1.106.3 (`memory/state.md`), so the findings above were checked against
  a newer source than the one running. V1 (the pre-call hook behaviour) was confirmed on 1.106.3.
- **2026-10-25, smoke runs.** With `qwen3.5:9b` as primary: `stack.py smoke --dept docs` passed 8 of 8 in 71 s warm. It
  covered an OpenAI tool call and tool-result round trip, an Anthropic `/v1/messages` call with `thinking`, `text` and
  `tool_use` blocks, the router alias, embeddings and the orchestrator MCP. Chat took 2.8 s. On the 35B primary the
  same smoke passed 8 of 8 in 153 s with a 28.6 s chat.
- **2026-10-26, V1.** `async_pre_call_deployment_hook` runs after routing and fallback selection, before the provider
  call, on both endpoints, and sees the chosen deployment. Raising a plain exception returns 500 and the router retries
  it three times. Confirmed in source and a test proxy.
- **2026-10-26, V2.** `user_header_name` end-user mapping failed open without Postgres. `custom_auth` plus
  `enable_post_custom_auth_checks` enforced model limits with a 403. The claim that headers alone can enforce access
  was refuted.
- **2026-10-26, V3.** Open WebUI 0.12.3 forwards a chat id and user headers when
  `ENABLE_FORWARD_USER_INFO_HEADERS=true`; some calls lack a chat id.
- **2026-10-26 late evening.** After the private-only build, a full `smoke` passed 6 of 7 in 28 minutes (first chat
  448 s, OpenAI tool call timed out) while requests queued behind model warm-up. A warm `smoke --dept docs` passed
  8 of 8 in 72 s with a 3.4 s chat. Direct Ollama decoded at 80 tok/s.
- **Not yet run.** `scripts/claude-local.ps1` as a live session. Only the gateway's `/v1/messages` path was smoke-tested
  (`memory/state.md`, open item 5).

## Open questions

- Does Claude Code pass a non-Claude `model:` string from subagent frontmatter to the gateway unchanged? The docs imply
  yes but never say so (research-claude-code-local.json).
- Does the gateway's `/v1/messages` to `ollama_chat/` path return tool calls and thinking blocks without loss under a
  live Claude Code session? One upstream issue (#24091, on LiteLLM 1.82.4) reported dropped tool calls; no live test here.
- Do the complexity router's stall and plan-mode features fire on the `/v1/messages` surface? The research found no
  end-to-end test.
- Does Ollama reject Claude Code's `role: system` entries or `effort` field, and how much latency do retries add?
- What is the right pinned LiteLLM version? The research could not confirm the image-tag convention.
- When is there enough traffic to justify Postgres and `adaptive_router`? That also unlocks virtual keys and the admin UI.
- The Haiku model ID conflict (see misconceptions) stays open until a cloud key exists.

## Sources and further reading

Only URLs recorded in the repo's research files are listed. Titles marked "(title not recorded)" were not stored.

| Title | Org, year | Link | Good for |
|---|---|---|---|
| LLM gateway (Claude Code docs) | Anthropic, 2026 | https://code.claude.com/docs/en/llm-gateway | Billing rules and environment variables when pointing Claude Code at a gateway |
| LLM gateway protocol (Claude Code docs) | Anthropic, 2026 | https://code.claude.com/docs/en/llm-gateway-protocol | What a gateway must support: streaming, headers, hint headers, `/v1/models` |
| Anthropic API compatibility (Ollama docs) | Ollama, 2026 | https://github.com/ollama/ollama/blob/main/docs/api/anthropic-compatibility.mdx | Which `/v1/messages` fields Ollama supports and which it does not |
| LiteLLM Ollama provider code (title not recorded) | BerriAI, 2026 | https://github.com/BerriAI/litellm/tree/main/litellm/llms/ollama | `ollama_chat/` versus `ollama/` behavior |
| LiteLLM Anthropic endpoints code (title not recorded) | BerriAI, 2026 | https://github.com/BerriAI/litellm/tree/main/litellm/proxy/anthropic_endpoints | How `/v1/messages` bridges to other providers |
| LiteLLM custom logger source | BerriAI, 2026 | https://github.com/BerriAI/litellm/blob/main/litellm/integrations/custom_logger.py | Hook signatures and what each can return |
| LiteLLM complexity router source | BerriAI, 2026 | https://github.com/BerriAI/litellm/tree/main/litellm/router_strategy/complexity_router | Tiers, classifier types, escalation settings |
| LiteLLM adaptive router source | BerriAI, 2026 | https://github.com/BerriAI/litellm/tree/main/litellm/router_strategy/adaptive_router | The learned-routing upgrade path |
| LiteLLM router source | BerriAI, 2026 | https://github.com/BerriAI/litellm/blob/main/litellm/router.py | Retries, fallbacks and cooldown logic |
| LiteLLM docker-compose file | BerriAI, 2026 | https://github.com/BerriAI/litellm/blob/main/docker-compose.yml | What needs `DATABASE_URL` |
| RouteLLM repository | LMSYS, 2026 | https://github.com/lm-sys/RouteLLM | Learned router for strong versus weak models |
| semantic-router repository | Aurelio Labs, 2026 | https://github.com/aurelio-labs/semantic-router | Intent-based semantic routing |

Project files: `docs/research/research-routing-proxy.json`, `docs/research/research-claude-code-local.json`,
`docs/research/anthropic-facts-2026-10.md`, `docs/ORCHESTRATOR-DESIGN.md` sections 4, 7, 8 and 11,
`docs/plans/SHARED-COMPONENTS.md` S3 and section 7, `memory/lessons.md`.

## Changes

- 2026-11-01: first version.
