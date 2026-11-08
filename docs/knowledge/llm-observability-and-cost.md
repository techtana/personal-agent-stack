# LLM observability and cost

Last updated: 2026-11-01. Companion file: [Coding agents and self-improvement](coding-agents-and-self-improvement.md),
which explains the retrospective loop that reads the records described here.

## 1. What this is and why the project needs it

Observability means being able to answer, after the fact, "what did the stack do, how fast, and what did it cost?"
without guessing. The project needs it for three reasons. The owner wants to know which department and which model
handled each request and whether the local GPU or a paid cloud model did the work. The weekly retrospective needs
numbers to propose routing changes. And the owner's data is private, so the records must show what happened without
storing what was said. This file explains tokens, prices, speed and traces from the ground up, then shows which part of
the repo measures each one and which parts the plans remove.

## 2. The ideas, built up from zero

### 2.1 Tokens: the unit everything is measured in

Think of an electricity meter. You do not pay per appliance or per hour of use; you pay per kilowatt-hour that passed
through the meter. Language models have a similar meter. They do not read letters or words. They read **tokens**:
short pieces of text, often a word or part of a word. In English one token is a few characters; code and other
languages usually need more tokens per word. The model's input is counted in tokens, and so is its output.

Three counts matter:

- **Input tokens** (also called prompt tokens): everything sent to the model in one request. In an agent this is not
  just your question. It is the instructions, the tool list, the conversation so far and every file the agent has read.
- **Output tokens** (completion tokens): what the model writes back, including any hidden reasoning it does first.
- **Cached tokens**: input tokens the provider has already processed in an earlier request and can reuse. This is
  **prompt caching**. The reuse works only for an identical start of the prompt (a prefix), and it is cheaper.

Where the meter analogy stops: a kilowatt-hour is a physical quantity. A token count depends on the **tokenizer**, the
rule that splits text, and each model family has its own. The same sentence is a different number of tokens on a
different model, so token counts are comparable only inside one model.

Agents make this matter more than chat does. Each loop turn resends the whole growing context as input, so an agent
doing twenty steps pays for the early context twenty times, unless caching applies. Output is usually much smaller than
input.

### 2.2 How API pricing works

A cloud provider charges per million tokens (written MTok), with one price for input and a higher one for output.
In words: the cost of a request is the input tokens divided by one million times the input price, plus the output
tokens divided by one million times the output price.

As a formula: cost = (T_in / 1,000,000) x P_in + (T_out / 1,000,000) x P_out, where T_in and T_out are token counts
(tokens) and P_in and P_out are prices in US dollars per million tokens.

The project's recorded list prices (`docs/research/anthropic-facts-2026-10.md`, cached 2026-10-06 and verified
in-session 2026-10-24), in dollars per MTok as input / output:

| Model | Input | Output |
|---|---|---|
| Fable 5.1 | 10 | 50 |
| Opus 5.5 | 4 | 20 |
| Sonnet 5.5 | 2 | 10 |
| Haiku 5.5 (prompts up to 100K tokens) | 0.10 | 0.50 |

**Worked example.** One agent turn sends 20,000 input tokens and gets 1,500 output tokens back. These token counts are
made up for the example; the prices are from the table.

- Sonnet 5.5: input = 20,000 / 1,000,000 x 2 = 0.04. Output = 1,500 / 1,000,000 x 10 = 0.015. Total = $0.055.
- Haiku 5.5: input = 20,000 / 1,000,000 x 0.10 = 0.002. Output = 1,500 / 1,000,000 x 0.50 = 0.00075. Total = $0.00275.

The same turn is 20 times cheaper on Haiku 5.5 (0.055 divided by 0.00275). I derived that ratio myself from the two
totals. Whether Haiku does the job as well is a separate question; price says nothing about quality.

**Caching example.** Suppose 18,000 of the 20,000 input tokens repeat the previous request's prefix and the provider
serves them from cache. On Opus 5.5 the list input price is $4 and the cache-read price is $0.20 per MTok (both the
facts file and the pricing page extract in `docs/research/` agree on these two). Without caching the input costs
20,000 / 1,000,000 x 4 = $0.08. With caching it costs (2,000 / 1,000,000 x 4) + (18,000 / 1,000,000 x 0.20) = 0.008 +
0.0036 = $0.0116, about 86 percent less (derived by me). The first request that writes the prefix into the cache is
priced higher than plain input; the research records $5 per MTok as the Opus 5.5 cache-write price (pricing page
extract). **Disputed number:** for Sonnet 5.5 the facts file gives a cache-read price of $0.20 while the pricing page
extract in the research gives $0.10. Check the current price page before using either.

Two other levers recorded in the facts file: the Batch API is 50 percent cheaper for work that can wait (the
retrospective and nightly evals are examples), and `output_config.effort` (low to max) is "the primary cost lever
within a model", because less effort means fewer hidden reasoning tokens. Since 2026-10-21 passing `temperature`,
`top_p` or `top_k` to Claude models returns HTTP 400.

**Subscription is not API billing.** Claude Code on a Max plan shows dollar figures that are computed locally from token
counts at list price. Anthropic's own docs, quoted in the research, say these are estimates and not relevant for billing
on a subscription; only the Console usage page is authoritative. Label such figures "API-equivalent". This stack has no
Anthropic API key on the reference machine, so the gateway's cloud cost is zero; Claude Code on the subscription is outside the
gateway entirely (`memory/state.md`).

### 2.3 What running locally costs

A local model has no per-token bill, so the gateway records a cost of zero for it (`input_cost_per_token: 0` in
`scripts/stacklib/litellm_build.py`). That zero is a billing fact, not an economic one. The real costs are electricity
while the GPU works, the purchase price of the hardware spread over its useful life, and the owner's time.

In words: the electricity cost of a request is the power drawn in kilowatts, times the hours of work, times the price
per kilowatt-hour. As a formula: cost = (W / 1000) x h x P, where W is average power in watts, h is time in hours and P
is the price per kWh. A purely hypothetical example: a machine drawing 200 W for one hour uses 0.2 kWh, so at a made-up
price of 0.20 per kWh it costs 0.04. **None of these inputs are measured here.** The repo records no wattage and no
electricity price: source not recorded. The research suggests that a team could set a small synthetic cost per token for
local models to make local and cloud comparable; the project did not do this. GPU power draw can be read from
`nvidia_smi_power_draw_watts`, which the `nvidia_gpu_exporter` tool exposes, but that exporter is documented and not
wired (`docs/ORCHESTRATOR-DESIGN.md` section 12).

The real reasons to run locally here are privacy, offline use and fixed cost, not savings. The research itself notes
that a cheap cloud tier (Haiku 5.5 at $0.10 / $0.50) usually beats a small local model on quality for almost no money,
and recommends local mainly for privacy, offline use, rate limits, autocomplete and embeddings (the project's lessons
add the mixture-of-experts tier).

### 2.4 Latency: three clocks

**Latency** is the waiting time. For a streamed chat answer it splits into parts you feel differently:

- **Time to first token** (TTFT): from sending the request until the first piece of the answer appears. It includes
  model load (if the model was not in memory), reading your prompt (**prefill**, also called prompt evaluation) and the
  first step of writing.
- **Decode speed**: how fast the answer then streams, in tokens per second (tok/s).
- **Total latency**: from request to the last token.

In words: tok/s is the number of output tokens divided by the time spent generating them. As a formula: tok/s =
N_out / t_decode, with N_out in tokens and t_decode in seconds. Ollama reports its times in nanoseconds
(`eval_count` and `eval_duration` for decode, `prompt_eval_count` and `prompt_eval_duration` for prefill,
`load_duration`, `total_duration`), so divide nanoseconds by 1,000,000,000 first (`docs/research/README.md`,
observability section, rated medium).

**Worked example**, using this machine's measurements in `memory/state.md` for qwen3.5:9b at 16,384 context: warm decode
51 to 52 tok/s and warm prefill 865 to 927 tok/s, measured with a 54-token prompt and 256 generated tokens. Prefill time
for 54 tokens is about 54 / 900 = 0.06 s. Decode time for 256 tokens is about 256 / 51.5 = 5.0 s. So a warm request takes
about 5 s in total (derived by me from those measurements). A cold start adds model load: 161 s at 16k and 130 s at 32k
in the same table, because the model reads from a USB drive. This is why "latency" without "warm or cold" means little.

Prefill and decode behave differently. Prefill is fast and grows with prompt length; decode is slower and grows with the
answer length. Agents send long prompts, so prefill and the first-token wait matter more for them than for chat.

### 2.5 Traces, spans and OpenTelemetry

A utility meter gives one number. A **trace** is closer to a receipt with line items: it follows one request through the
system. Each step is a **span**: a named piece of work with a start time, a duration and attributes (model, token counts,
status). Spans nest, so a request span can contain a "model load" span and a "decode" span. A trace is the tree of spans
for one request.

**OpenTelemetry** (OTel) is the vendor-neutral standard for emitting and shipping this data. A program emits spans, and
a collector or viewer receives them over a protocol called OTLP. The part that describes LLM calls, the "GenAI semantic
conventions" (attribute names such as `gen_ai.*`), is still marked "Development" stability. In June 2026 it was moved to a
separate repository without a tagged release (research note, rated high). Expect names to change.

A **viewer** stores and displays spans. **Phoenix** (Arize, Elastic License 2.0) is a single-process trace viewer with
local SQLite storage. The project used it as a spans viewer fed by LiteLLM's OpenTelemetry callback and by custom spans
from the request logger. On this machine Smart App Control blocked its compiled Python modules, and the plans remove it
(section 5).

**JSONL request logs** are the simpler option. JSONL means one JSON object per line, appended to a file per day. It
needs no server, survives restarts, and you can read it with any tool. The cost is that you build every view yourself.
The project uses both: a JSONL file written by the gateway callback, and (while it lasts) spans in Phoenix.

**The LiteLLM request log** is the gateway's built-in record, stored in PostgreSQL when a database is attached, with an
admin UI. It tracks spend, tokens and latency per request and per virtual key. On this machine the admin UI fails with
"Not connected to DB!" because no Postgres is attached (`memory/state.md`, open item 9). The plans make this log the
replacement for the JSONL files.

### 2.6 What to log, and what not to log

The prompt text of a request is the most useful thing for debugging and the most dangerous thing to keep. It holds the
owner's code, files and questions, and a trace store is queried, copied and backed up more freely than a chat. The rule
the project follows: log the shape of a request, not its content. Safe fields are the time, the model alias asked for,
the model that served it, token counts, durations, cost, status, a short error string and the routing decision.
Sensitive fields are the prompt, the completion, file contents and tool output.

Two caveats. First, a "no prompt text" claim is only as good as the code. The gateway callback in
`infrastructure/litellm/custom_callbacks.py` says it stores no prompt or completion text, and the fields it writes
agree: checked against the code on 2026-11-01, the record holds metadata, token counts, timings and routing, plus an
error string cut to 300 characters on failure. The plans' removal table calls it "JSONL traces with prompt text"; that
label looks wrong. The error string can still carry a fragment of a request, so sample a log before trusting it.
Second, metadata can leak too: a user id, an email or a chat id identifies a person. Record the least that answers the
question, and set a retention period (none is defined in the repo).

### 2.7 Per-process CPU, memory and GPU

Request logs say what the models did. They do not say what the machine is doing. For that you sample the operating
system: how much processor time, memory and GPU each process uses. Local inference is bounded by memory more than by
anything else (the lessons record that RAM pressure, not VRAM, was the binding constraint for the 35B model), so a
resource view tells you why a model is slow.

`scripts/stacklib/process_metrics.py` does this for the tray's Resources tab. It uses the `psutil` library for CPU
percent and resident memory (RSS, the memory physically held by the process), and asks Windows for GPU engine
utilisation and dedicated GPU memory per process through a PowerShell performance-counter query. On other systems it
reads `nvidia-smi pmon`. Two details worth knowing: CPU percent is measured between refreshes, so a process seen for the
first time shows no CPU figure; and GPU utilisation is summed across a process's engines and capped at 100 percent.

## 3. Rules of thumb and typical numbers

- Price per MTok, input / output: Haiku 5.5 0.10 / 0.50; Sonnet 5.5 2 / 10; Opus 5.5 4 / 20; Fable 5.1 10 / 50
  (`docs/research/anthropic-facts-2026-10.md`).
- Batch processing saves 50 percent (same file). Prompt caching reads are far cheaper than fresh input (Opus 5.5: 0.20
  versus 4). Caches are scoped to one model, and a cache hit is best-effort, not guaranteed (research note on the
  Batch API, rated high).
- Check `usage.cache_read_input_tokens` in the response to confirm that caching worked (facts file).
- Decode on this machine: about 51 to 52 tok/s for the 9B model; about 25 tok/s for the 35B mixture-of-experts model
  (`memory/state.md`, benchmarks of 2026-10-25). The 39 to 47 tok/s community figure for the 35B was not reproduced
  (the research verification marks that claim "contested").
- Cold model load from the USB drive: 130 to 331 s depending on the model and context (`memory/state.md`).
- Enterprise average for Claude Code at API rates is about $13 per developer per active day (Anthropic cost docs, via the
  research summary). This is not this project's figure.
- Phoenix with SQLite: the research estimated 1 to 3 GB of RAM from third-party sizing; the vendor gave no figure.
- Langfuse (a heavier trace and evaluation platform) needs about 16 GiB of RAM and six containers; the research judged
  that too heavy beside Ollama on a 32 GB machine.

## 4. Common misconceptions and edge cases

- "Local is free." The per-token price is zero. Electricity, hardware wear and the owner's time are not, and none are
  measured here (source not recorded).
- "Token counts are the same everywhere." They depend on the tokenizer. Compare counts only within one model.
- "tok/s is one number." Prefill and decode differ by an order of magnitude. A tray figure that mixes them misleads.
  Also, `scripts/stacklib/usage.py` computes tok/s from Ollama's decode time when the log has it, and falls back to
  wall-clock latency otherwise, which understates speed because wall-clock includes load and prefill.
- "A cheaper model is always cheaper." An agent that needs three tries on a cheap model can cost more than one try on a
  stronger one. The facts file says to measure the most capable model at lower effort before building a cascade.
- "Claude Code's dollar figure is my bill." On a subscription it is not. It is an estimate at list price.
- "The cost field covers everything." Cost in the log is the gateway's `response_cost`. Claude Code sessions on the
  subscription, and any usage outside the gateway, never appear in it.
- "Traces mean prompts are saved." Only if the logger writes them. The design intends no prompt storage; verify it
  (section 2.6).
- Two clocks differ (our reading, not measured separately): the gateway's latency includes queueing and routing,
  Ollama's `total_duration` does not. The first
  full smoke test of 2026-10-26 took 28 minutes because early requests queued behind model warm-up, while a warm run took
  72 seconds (`memory/state.md`).
- Each record's `ts` is UTC, but the file name is the proxy host's local date (`custom_callbacks.py`). `usage.py` reads
  one extra day and then filters by local day, so a "today" window can span two files.
- Streaming and failed requests can lack usage fields; some OpenAI-compatible Ollama paths drop the timing fields
  (research note on the Ollama API, rated medium).
- OTel GenAI attribute names are still changing. Keep the mapping in one place (research recommendation).

## 5. How the project uses it

**Gateway records.** `infrastructure/litellm/custom_callbacks.py` (a LiteLLM `CustomLogger`) appends one JSON line per
request to `traces/litellm/YYYY-MM-DD.jsonl`. Fields: time, status, requested alias, served model, provider, process
name, tokens, cost, latency, Ollama's load, prefill, decode and total times (nanoseconds converted to milliseconds),
cache hit, the routing decision (tier, cause, signals), Claude Code's request-class and agent-type hint headers, key
alias and a short error. It can also emit the timing phases as spans to Phoenix when `OTEL_ENDPOINT` is set. Failures in
logging are caught so they never break the proxy.

**Claude Code hook records.** `scripts/hooks/log_turn.py` appends one line per Stop, SubagentStop and test-run event to
`traces/claude/`: agent type, tool name and duration, test pass or fail from output patterns, the `ESCALATE` sentinel
and message size, plus the first 200 characters of the last assistant message and the first 300 characters of each
Bash command. Its docstring says no prompt or file contents are stored; those two fields mean short fragments are.

**Reading them.** `scripts/stacklib/traces.py` loads the JSONL files. `uv run scripts/stack.py why-routed --last 20`
prints one line per request: time, alias asked, model served, tier, cause, signals, tokens, cost, latency and class. Use
it to see why a request went to a given model. `uv run scripts/stack.py retro --days 7` feeds the same rows into the
retrospective ([loop explained here](coding-agents-and-self-improvement.md)).

**Per-alias usage in the tray.** The Usage tab calls `scripts/stacklib/usage.py`. It groups requests by gateway alias
(`local-primary`, `docs`, ...) or by served model, and reports requests, errors, input and output tokens, average
latency, tok/s (generated tokens divided by generation time), cost, last use and a tokens-per-day series.

**Per-process and per-model aggregation.** `scripts/stacklib/metrics.py` groups the same JSONL records by process and
model over fixed windows (1 hour, 24 hours, 7 days, 30 days, all time), summing requests, tokens and cost and averaging
load, prefill, decode and total durations. At the time of writing only the unit tests import it
(`tests/test_metrics.py`); the tray's Usage tab uses `usage.py`. Treat `metrics.py` as built but not yet wired into the
window. `scripts/stacklib/process_metrics.py` supplies the Resources tab (section 2.7).

**Benchmarks.** `uv run scripts/stack.py bench` measures tok/s and the GPU/CPU split of the primary model through Ollama.

**What is slated for removal** (`docs/plans/SHARED-COMPONENTS.md` section 5, package R, once the privacy-gate service
runs): Phoenix (the service, the OTel callback and the tray link); the JSONL trace callback
`custom_callbacks.py`, `scripts/stacklib/traces.py`, `why-routed` and its skill; and `scripts/hooks/log_turn.py` with its
Claude Code hooks, replaced by Claude Code's own OpenTelemetry export to a local collector if the owner wants development
traces. LiteLLM's PostgreSQL request log and admin UI, which store no prompt text, take over, and `retro` reads that log
plus Open WebUI feedback. Anything in this file about JSONL traces describes the current state, not the end state. The
Usage tab and `metrics.py` would need a new data source.

Design history and reasons: [../design/DECISIONS.md](../design/DECISIONS.md) (the removals are under 2026-10-26).

## 6. What we found

- **2026-10-24.** The research recommended a gateway-centric design: LiteLLM in front of Ollama and the cloud, Phoenix as
  the trace store, custom per-token prices (zero for Ollama), and Anthropic's published Prometheus and Grafana compose
  for metrics. The repo implemented the gateway and the JSONL callback; Prometheus, Grafana and the GPU exporter were
  documented but not wired (`docs/ORCHESTRATOR-DESIGN.md` section 12).
- **2026-10-25.** Benchmarks on the reference machine: qwen3.5:9b decodes at 51 to 52 tok/s and uses about 5.9 GB of VRAM at 16k
  context; the 35B mixture-of-experts model decodes at about 25 tok/s and leaves about 1 GB of RAM free. RAM pressure,
  not VRAM, was the limit (lessons 2026-10-25).
- **2026-10-26.** Smart App Control blocked compiled modules inside the Phoenix tool environment (pyarrow, sqlalchemy,
  pandas), so Phoenix stopped starting on this machine, after it had run the day before. LiteLLM's OpenTelemetry callback
  then had no collector. Phoenix later ran again after the private-only build was deployed (state.md lists all five
  services up that evening), then the plans slated it for removal (lesson 2026-10-26; SHARED-COMPONENTS V9).
- **2026-10-26.** Full smoke test 6 of 7 passed in 28 minutes while the first requests queued behind warm-up. A warm
  single-department smoke passed 8 of 8 in 72 seconds with a 3.4 s chat reply (`memory/state.md`).
- **2026-10-26.** LiteLLM's per-user lookup fails open when no database is attached, and the error is logged at debug
  level, so nothing visible warns you (lesson). Observability has the same trap: a missing database yields empty
  dashboards, not errors.
- **2026-10-26/27.** The tray gained a Usage tab (per-alias requests, tokens, latency, tok/s, cost) and a Resources tab with
  per-process CPU, memory and GPU. Verified by screenshots and a headless apply; the live tray was not yet restarted on
  the new code (`memory/state.md`).
- **2026-11-01.** The desktop app's built-in browser reports a 0x0 viewport and records no Largest Contentful Paint while
  its pane is hidden. Set a viewport size before measuring a page, and treat zero results as invalid (lesson). The same
  rule applies to any metric: a zero may mean "not measured".

## 7. Open questions

- What does local inference actually cost? Needs measured wattage, an electricity price and a hardware lifetime. Source
  not recorded.
- Can the 300-character error string in a gateway trace carry request content? Inspect failure records to settle it.
- What replaces the Usage tab and `metrics.py` after the JSONL removal, and does the LiteLLM request log carry the Ollama
  timing fields (load, prefill, decode)? Not established.
- Does LiteLLM's Prometheus endpoint work without an enterprise licence in the installed version? The research found
  conflicting evidence (a 2024 commit gated it; current docs do not).
- Which Anthropic cache-read price is current for Sonnet 5.5, 0.10 or 0.20? Sources disagree (section 2.2).
- Which Haiku ID and price apply to the owner's account? The research notes list both `claude-haiku-5-5` and
  `claude-haiku-4-5-20251001`.
- Is Anthropic's server-side API tracing available to an individual Console account? Open in the research.
- How long should request logs be kept? No retention rule exists.
- Whether the owner is on Max 5x or 20x decides whether included API credits fund the department agents (research
  open question); `memory/state.md` records Max 5x with no API key on this machine.

## 8. Sources and further reading

All links below are recorded in `docs/research/` or the repo. None were re-fetched for this file.

- Anthropic model prices and behaviours, Anthropic via the project's `claude-api` skill cache, 2026. List prices, effort,
  caching, batch. In the repo: [anthropic-facts-2026-10.md](../research/anthropic-facts-2026-10.md).
- Claude pricing page, Anthropic, 2026. List prices, cache and batch discounts, Max plan credits. https://claude.com/pricing
- Claude Code costs documentation, Anthropic, 2026. Why the dollar figures are estimates on a subscription. https://code.claude.com/docs/en/costs
- Claude Code monitoring documentation, Anthropic, 2026. OpenTelemetry metrics and events for Claude Code. https://code.claude.com/docs/en/monitoring-usage
- Batch processing documentation, Anthropic, 2026. Half-price asynchronous requests. https://platform.claude.com/docs/en/build-with-claude/batch-processing
- Usage and Cost Admin API, Anthropic, 2026. Needs an organisation admin key; unavailable to individual accounts. https://platform.claude.com/docs/en/manage-claude/usage-cost-api
- LiteLLM Prometheus metrics documentation, BerriAI, 2026. Metric names and labels. https://raw.githubusercontent.com/BerriAI/litellm-docs/main/docs/proxy/prometheus.md
- LiteLLM custom pricing documentation, BerriAI, 2026. Zero cost for Ollama models. https://raw.githubusercontent.com/BerriAI/litellm-docs/main/docs/proxy/custom_pricing.md
- Arize Phoenix self-hosting (Docker), Arize, 2026. Single container, SQLite, OTLP ports. https://raw.githubusercontent.com/Arize-ai/phoenix/main/docs/phoenix/self-hosting/deployment-options/docker.mdx
- Langfuse Docker Compose deployment, Langfuse, 2026. Sizing for the heavier alternative. https://raw.githubusercontent.com/langfuse/langfuse-docs/main/content/self-hosting/deployment/docker-compose.mdx
- OpenTelemetry GenAI semantic conventions, OpenTelemetry project, 2026. Attribute names, still in development. https://github.com/open-telemetry/semantic-conventions-genai
- Open WebUI monitoring and OpenTelemetry documentation, Open WebUI, 2026. What its export covers. https://raw.githubusercontent.com/open-webui/docs/main/docs/reference/monitoring/otel.md
- Ollama API documentation, Ollama, 2026. Timing fields in nanoseconds, `/api/ps`. https://raw.githubusercontent.com/ollama/ollama/main/docs/api.md
- nvidia_gpu_exporter, utkuozdemir, 2026. GPU power and memory metrics on Windows. https://raw.githubusercontent.com/utkuozdemir/nvidia_gpu_exporter/master/README.md
- In the repo: [research summaries](../research/README.md) (observability section), [shared components plan](../plans/SHARED-COMPONENTS.md)
  (section 5), [orchestrator design](../ORCHESTRATOR-DESIGN.md).

## Changes

- 2026-11-01: first version.
