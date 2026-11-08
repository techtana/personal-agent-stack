# Running a large language model on one consumer GPU

## What this is and why the project needs it

A language model is a very large table of numbers plus a small program that uses the table to predict the next word.
Running one "locally" means your own computer holds the table and does the arithmetic, so your text never leaves the
machine. The catch is that the table is big (gigabytes) and the arithmetic has to touch much of it for every word
produced. A gaming graphics card has fast but limited memory; the rest of the PC has more memory that is slower.
This project promises to keep private work on the owner's own hardware (an RTX 3060 with 12 GB of video memory and
32 GB of ordinary RAM), so it has to fit useful models into that budget and keep them responsive. Almost every
setting in `machines/*.yaml`, the Ollama environment variables and the gateway model aliases is a decision about that
budget. This page explains the ideas behind those settings so you can read them without guessing.

## The ideas, built up from zero

### Weights, parameters and bytes

Think of a model as a huge spreadsheet of numbers. Training adjusts the numbers until the model's guesses are good.
After training, the numbers are fixed. They are called **weights**, and each one is a **parameter**. A "9B" model has
about nine billion of them. (The exact count for Qwen3.5-9B is not recorded in the repo; the worked sizes below assume
9.7 billion as an illustration.)

Parameters count numbers. To know how much memory the model needs, you need bytes, and that depends on how many bits
each number is stored in. The rule is:

    size_bytes = parameters x bits_per_weight / 8

Here `parameters` is a count, `bits_per_weight` is bits per number, and dividing by 8 converts bits to bytes. Training
usually stores each weight in 16 bits. A 9.7-billion-parameter model at 16 bits is 9.7e9 x 16 / 8 = 19.4 GB. That does
not fit a 12 GB card. At about 4.5 bits per weight (a typical 4-bit scheme with a little overhead) it is
9.7e9 x 4.5 / 8 = 5.5 GB. That fits with room to spare. (Both sizes are derived here, not measured.) The real
download for `qwen3.5:9b` is 6.6 GB ([`machines/_defaults.yaml`](../../machines/_defaults.yaml)), which works out to
about 5.4 bits per weight (also derived). The extra comes from parts kept at higher precision, such as the table that
maps tokens to numbers. The research notes put the plain Q4_K_M file near 5.7 GB
([research-local-models.json](../research/research-local-models.json), Qwen3.5-9B claim).

The spreadsheet analogy stops here: a spreadsheet's cells do not change when you shrink them, but weights lose a
little accuracy when you store them in fewer bits. That is the next idea.

### Quantization and GGUF

**Quantization** means storing each weight with fewer bits by rounding it to the nearest of a smaller set of values.
Picture a photograph saved at lower colour depth: it is smaller, and for most pictures you hardly see the difference.
Four bits give 16 possible values per weight, so the scheme groups weights into small blocks and stores a shared scale
for each block to keep the rounding error low. Names such as **Q4_K_M** describe a scheme: "Q4" is roughly four bits,
"K" is a block-based method family from llama.cpp, "M" is a medium mix that keeps some important tensors at higher
precision. Related names (`Q8_0`, `IQ4_XS`, `UD-Q4_K_XL`) are other points on the size-versus-accuracy curve. The exact
bits per weight of each scheme are not recorded in the repo; source not recorded.

**GGUF** is the file format llama.cpp (the engine under Ollama) reads. One GGUF file holds the quantized weights, the
model's settings and its vocabulary, so a single file is enough to run the model. Ollama stores GGUF files as "blobs"
in the model store (`D:\ollama\models` on this machine).

The analogy stops where accuracy matters: a lower-bit model is not just "slightly blurrier". It can fail in specific
ways, such as less reliable tool calls. Published benchmark scores are usually for the full-precision model, not the
4-bit file you run (see the misconceptions below).

### Three places to keep the weights: VRAM, RAM and disk

A computer has tiers of memory, like a workshop. **VRAM** (video memory, on the graphics card) is the workbench: small
and very fast. System **RAM** is the shelf behind you: bigger, slower to reach. **Disk** is the storeroom down the
hall: biggest, slowest. The GPU can only compute on what is on its bench, and the CPU works from the shelf.

On the owner's machine the bench is 12 GB (12,288 MiB), but Windows takes part of it for the desktop before any model
loads. The machine profile records 1,135 MiB of idle use (`machines/<HOST>.yaml`);
`memory/state.md` says about 1.0 GB. This is the Windows display driver model (WDDM) at work: the desktop, browser and
video decoding all use video memory, and a model cannot take it back. The usable bench is therefore about 11 GB. The
shelf is 31.9 GB of DDR4-2133 in two 16 GB modules, but the usual desktop apps leave only about 11-12 GB free before
a model loads ([`memory/state.md`](../../memory/state.md)). The storeroom is a USB SSD for models (`D:`) and an NVMe
SSD for the system (`C:`); loads from `D:` are limited by the USB link.

    +-----------------------------------------------------------+
    |  DISK (D: USB SSD)   all GGUF files, e.g. 6.6 GB / 22 GB  |
    +-----------------------------+-----------------------------+
                                  | read once, at load
                 +----------------v----------------+
                 |  SYSTEM RAM (shelf, ~34 GB/s)    |   MoE experts that do not
                 |  page cache, expert tensors      |   fit on the bench
                 +----------------+----------------+
                                  | PCIe (small transfers only)
                 +----------------v----------------+
                 |  VRAM (~360 GB/s*, ~11 GB)       |   dense weights, attention
                 |  weights + KV cache + buffers    |   weights, KV cache
                 +----------------------------------+

\* The 360 GB/s figure is the RTX 3060's published spec; it is not recorded in the repo.

Where the model sits decides the speed. Weights on the bench are read fast. Weights on the shelf are read at the
shelf's speed. The next sections explain why speed is a matter of how fast bytes can be read.

### Generating text: tokens, prefill and decode

Models do not read letters or words; they read **tokens**, small pieces of text (a common word is one token, a long
word several). A model produces its answer one token at a time, and each new token needs a pass through the weights.
Two phases follow.

**Prefill** is reading your prompt. All prompt tokens can be processed in one batch, so the GPU's many cores stay
busy. Prefill speed is measured in prompt tokens per second. **Decode** is writing the answer, one token after
another, where each token depends on the one before and cannot be batched. Decode speed in tokens per second
(tok/s) is the figure people mean when they say a model is "fast". The project's `bench` command reports both: for
the 9B model it measured 51-52 tok/s decode and 865-927 tok/s prefill on 2026-10-25. Prefill is roughly 17 times
faster per token (derived: 900 / 52) because it is batched.

For reading along in chat, 25 tok/s feels fluent (our judgement, not a measured threshold). Agent loops (many tool calls,
long outputs) feel the difference more, so the project cares about the gap between 25 and 52.

### Why decode is bound by memory bandwidth

Imagine a cook who must read the entire recipe book aloud, page by page, to cook one dish, and must do it again for
every dish. The cook's hands are fast; reading the book is the slow part. In decode, producing one token means reading
(almost) every active weight once. The arithmetic per byte is small, so the processor waits on memory. The speed limit
is then:

    tokens_per_second  <=  memory_bandwidth / bytes_read_per_token

`memory_bandwidth` is how many bytes per second the memory can deliver (GB/s). `bytes_read_per_token` is the size of
the weights needed for one token (GB). The result is an upper bound; real speed is lower because of caches, the KV
cache reads (below) and other overheads.

Worked example with the dense 9B model, whose download is 6.6 GB:

- On the RTX 3060's GDDR6, at 360 GB/s: 360 / 6.6 = about 55 tok/s. The measured decode was 51-52 tok/s
  ([`memory/state.md`](../../memory/state.md), Benchmarks). The estimate is close, which supports the idea. The
  360 GB/s figure is the card's published specification; it is not recorded in the repo, so check it against the
  vendor page.
- On the CPU side, dual-channel DDR4-2133: each channel moves 8 bytes per transfer and the memory does 2,133 million
  transfers per second, so one channel gives 2.133e9 x 8 = 17.1 GB/s and two give about 34 GB/s (derived here). The
  same 6.6 GB model would top out near 34 / 6.6 = about 5 tok/s. That is why a model that runs from system RAM feels
  slow, and why the machine notes call DDR4-2133 the bottleneck for CPU-side experts.

The analogy stops at the limit being fixed: a smaller file (more aggressive quantization) raises the bound, because
fewer bytes are read per token. That is a main reason quantization speeds things up as well as shrinking them.

### The KV cache and why context length costs memory

When the model writes token number 1,000 it must "look back" at the previous 999. Recomputing everything about those
tokens each time would be wasteful, so it saves a compact summary per token, per layer, called the **KV cache** (keys
and values, the two vectors attention uses). The cache is the model's working memory for the conversation, like notes
on a whiteboard that grow with every line.

**Context length** (`num_ctx` in Ollama) is the number of tokens the whiteboard can hold: prompt, history and answer
together. Memory for the cache grows in direct proportion to it. The formula the research notes use is:

    kv_bytes_per_token = 2 x layers x kv_heads x head_dim x bytes_per_value

`2` counts keys and values. `layers` is how many attention layers keep a cache. `kv_heads` is the number of
key/value "heads" (a design choice of the model). `head_dim` is the vector length per head. `bytes_per_value` is 2
for 16-bit values and about 1 for `q8_0`. Total cache = `kv_bytes_per_token` x `num_ctx`.

Worked example from the research notes ([research-inference-engine.json](../research/research-inference-engine.json),
KV claim): Qwen3-14B has 40 layers, 8 KV heads and head_dim 128. That gives 2 x 40 x 8 x 128 x 2 = 163,840 bytes, or
160 KiB per token at 16 bits. At 32,768 tokens that is 5.0 GiB, and `q8_0` halves it to 2.5 GiB. For the project's own
Qwen3.5-9B the research notes infer about 32 KiB per token (8 full-attention layers x 4 KV heads x 256; medium
confidence, "inferred from library defaults"), so about 1.0 GiB at 32k in 16-bit and about 0.5 GiB with `q8_0`.
Newer models mix a few full-attention layers with other layer types, or use sliding windows, so their caches are far
smaller than older designs of the same size. That is why 32k context is affordable here.

Two settings follow. **Flash attention** (`OLLAMA_FLASH_ATTENTION=1`) is a way of computing attention that avoids
building large intermediate tables, saving memory and time; Ollama's FAQ says cache quantization only takes effect
with it. **KV cache quantization** (`OLLAMA_KV_CACHE_TYPE=q8_0`) stores the cache in 8 bits, about half the size of
16-bit, with negligible quality loss per the FAQ (`q4_0` saves more and loses more). It applies to every model at once.

A hidden cost: the cache is reserved for the full `num_ctx` when the model loads, not as you fill it. Doubling
`num_ctx` doubles that block even if you only send short prompts. Each parallel request slot gets its own full block,
so `OLLAMA_NUM_PARALLEL=2` doubles the cache.

### Dense versus mixture-of-experts models

In a **dense** model every weight takes part in every token. Cost per token is proportional to file size, so the
bandwidth rule above applies to the whole file. A **mixture-of-experts (MoE)** model splits most of its layers into
many small sub-networks, the **experts**, plus a small "router" that picks a few for each token. Think of a hospital:
a dense model sends every patient past every doctor; an MoE model has a triage desk that sends each patient to a few
specialists out of hundreds.

An MoE model therefore has two sizes. **Total parameters** say how much must be stored. **Active parameters** say how
much is read per token. Qwen3.6-35B-A3B, the class-default primary, has 35 billion total and 3 billion active
parameters; its model card lists 256 experts per layer with 8 routed and 1 shared (quoted in
[verification-status.json](../research/verification-status.json), claim 1). The download is 22-23 GB, and a token
reads only about 3/35 of it.

Rough bound, derived here: the active share of the 23 GB file is about 23 x 3 / 35 = 2.0 GB per token. If all of that
came from DDR4 at 34 GB/s, the ceiling would be about 17 tok/s. In practice the attention layers and shared weights
sit in VRAM and only the experts that spilled out sit in RAM, so the measured 25 tok/s is above that pure-RAM bound.
This is crude (it ignores which tensors are where); treat it as an order of magnitude.

The trade-off: MoE gives the quality of a large model at the per-token cost of a small one, but it needs storage for
all experts. On a 12 GB card the experts do not fit, so they go to system RAM, and part of the model runs at RAM speed.

### Offloading experts to the CPU

Because only a few experts run per token, a good split is: put the layers every token uses (attention, the router,
the shared expert) in VRAM, and the many expert tensors in RAM, where the CPU runs them. The llama.cpp flag for this
is `--n-cpu-moe N` ("keep the MoE weights of the first N layers in the CPU", per the llama.cpp server README as
quoted in the verification notes). Community recipes in the research notes used values of 18-26 on this card. A plain
"layer split" (some whole layers on the GPU, the rest on the CPU) works too but is slower, because it moves attention
to the slow side as well.

### Ollama, llama-server and the fit step

**llama.cpp** is the open-source engine that runs GGUF models; `llama-server` is its web server. **Ollama** is a
friendlier wrapper: it manages downloads, loads and unloads models, and exposes OpenAI-style and Anthropic-style
endpoints. As of v0.40.x it starts upstream `llama-server` as a child process for every GGUF model (research claim in
[research-inference-engine.json](../research/research-inference-engine.json); the recency check in
[verification-status.json](../research/verification-status.json), claim 3, dates the change to 2026-05-29).

Two environment variables matter, both handled by `llama-server` itself:

- `LLAMA_ARG_FIT=on` turns on the **fit** step: at load time the server measures free memory and decides what goes on
  the GPU. For an MoE model the fit step is expert-aware: it puts expert tensors in system memory first, then
  back-fills leftover VRAM with experts (recency finding, claim 3).
- `LLAMA_ARG_N_CPU_MOE=N` is the manual override: it sets the `--n-cpu-moe` value. Ollama passes its environment to
  the child process, so the variable reaches `llama-server`. That is undocumented behaviour, which is why the decision
  record calls it a trade-off ([2026-10-24-ollama-only-inference.md](../decisions/2026-10-24-ollama-only-inference.md)).

An older research claim said Ollama had no expert-aware offload at all. The verifiers marked that claim as
majority-refuted for current versions: it was true of the older Ollama engine. The project followed the corrected
finding and runs one engine.

### mmap, and why Ollama turns it off on Windows with CUDA

**Memory mapping (mmap)** lets a program treat a file as if it were already in memory. The operating system loads
pages from the file only when they are touched and can drop them again under pressure, because it can always re-read
them from the file. Without mmap the program reads the file into ordinary ("anonymous") memory, which the system can
only free by writing it to the swap file.

The project found that Ollama 0.40 disables mmap by default on Windows with an NVIDIA GPU (the lesson cites
`server/sched.go`, case "windows_cuda"; [`memory/lessons.md`](../../memory/lessons.md), 2026-10-25). The reason is not
recorded in the repo. With mmap off, loading the 35B model copied 12.65 GB of expert tensors into anonymous memory
while only 11.3 GB was free. Windows paged, the load ran past Ollama's five-minute limit and the request failed with
HTTP 500. Sending `use_mmap: true` in the request options keeps the experts file-backed; together with
`OLLAMA_LOAD_TIMEOUT=15m` this made the load succeed.

The analogy for mmap is a library you consult page by page instead of photocopying the whole book first. It stops
working when memory is already scarce: file-backed pages still have to be re-read from the slow USB SSD if the system
evicts them, which is why the first reply after loading the 35B arrived at only 2.6 tok/s while pages faulted in.

### Load timeouts

Loading is separate from speed. Ollama waits for the server process to report ready, and gives up after
`OLLAMA_LOAD_TIMEOUT` (default 5 minutes). Reading 22 GB from a USB SSD under memory pressure can exceed that, so the
project sets 15 minutes (comment in [`machines/_defaults.yaml`](../../machines/_defaults.yaml)).

### Keeping models loaded: residency and sharing

Loading takes minutes (130 s for the 9B at 32k, 331 s for the 35B on this machine), so the project avoids reloading.
These settings control residency:

- `OLLAMA_KEEP_ALIVE` is how long an idle model stays loaded (default 5 minutes; the project uses 30 minutes; a
  request can pass `-1` to pin a model, which `local-fim` and `local-primary` do; `local-small` uses 30m).
  `keep_alive` is not a load option, so it does not stop tiers sharing a runner.
- `OLLAMA_MAX_LOADED_MODELS` caps how many models are resident at once (project: 2, so the autocomplete model plus one
  large model).
- `OLLAMA_NUM_PARALLEL` is the number of requests served at once per model (project: 1). With 1, a second request to
  the same model waits its turn, and the cache is allocated once.
- `OLLAMA_MAX_QUEUE` is how many requests may wait before Ollama answers HTTP 503 (project: 32; default 512).
- `OLLAMA_GPU_OVERHEAD` reserves VRAM that Ollama will not plan to use (project: 512 MiB, for the Windows desktop).

When a request needs a model that is not loaded, the scheduler predicts its memory use. If that exceeds 80% of free
memory, it unloads an idle model first ([research-inference-engine.json](../research/research-inference-engine.json),
different-model concurrency claim). On a 12 GB card, two different 9 GB models used in turn reload at every switch.

This explains the sharing rule. Ollama keys a loaded runner by the model file's path, not by the alias name. Two
gateway aliases that point to the same file share one runner and cost no extra VRAM, but only if their load options
(`num_ctx` and the others) are identical. If `local-primary` used 32,768 and `local-small` used 16,384 for the same
file, the runner would reload on every switch between them. The project recorded this on 2026-10-25 and now gives both
the same `num_ctx` ([`memory/lessons.md`](../../memory/lessons.md)).

### Autocomplete (FIM) and embedding models

Two small models do jobs a chat model should not. **Fill-in-the-middle (FIM)** models complete code at the cursor,
given the text before and after it. They use special marker tokens and must be trained on them. Continue's
documentation names Qwen2.5-Coder 1.5B as a good open choice (about 986 MB, sub-500 ms replies even on CPU; see
[research-local-models.json](../research/research-local-models.json)). The project uses the `-base` variant, pinned in
memory, because autocomplete must answer in a fraction of a second and a model that must be loaded first is useless
there. The Qwen3.5 small models have no documented FIM support (same source).

An **embedding model** turns a text into a list of numbers so that similar texts have nearby lists. It does not
write; it serves search and similarity checks. `nomic-embed-text` (274 MB) does this job here. Both are tiny next to
a chat model (a few hundred MB to about 1 GB), so they can sit beside the large model.

## Rules of thumb and typical numbers

| Rule | Usual range | Where it comes from |
|---|---|---|
| Weight size = params x bits / 8 | 4-bit schemes land near 4.5-5.4 bits per weight in practice | derived here; 6.6 GB download from [`machines/_defaults.yaml`](../../machines/_defaults.yaml) and [research-local-models.json](../research/research-local-models.json) |
| Decode tok/s <= bandwidth / bytes read per token | 9B on the 3060: bound about 55, measured 51-52 | derived here; measurement in [`memory/state.md`](../../memory/state.md); 360 GB/s is the published card spec, source not recorded |
| Dual-channel DDR4-2133 bandwidth | about 34 GB/s peak | derived here (2,133 MT/s x 8 bytes x 2 channels); real figure lower |
| KV bytes/token = 2 x layers x kv_heads x head_dim x bytes | 160 KiB (14B dense, 16-bit) down to about 20-32 KiB (newer hybrid designs) | [research-inference-engine.json](../research/research-inference-engine.json), [research-local-models.json](../research/research-local-models.json) |
| `q8_0` KV cache is about half of 16-bit | negligible quality loss; `q4_0` is a quarter, more loss | [Ollama FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx), via the research notes |
| Ollama default context under 23 GiB of VRAM | 4,096 tokens | research claim on `server/routes.go`; too small for agents, so the project sets `OLLAMA_CONTEXT_LENGTH` |
| Usable VRAM on this card | about 11 GB of 12 GB | idle use 1,135 MiB, `machines/<HOST>.yaml` |
| Free RAM before a model loads | about 11-12 GB with the usual desktop apps open | [`memory/state.md`](../../memory/state.md) |
| Community speed of the 35B MoE on a 3060 12 GB | 39-47 tok/s, on faster RAM | disputed; see below |
| Cold load of the 9B / 35B here | 130-161 s / 331 s | [`memory/state.md`](../../memory/state.md), Benchmarks |
| Idle residency window | 5 min default; 30 min in this project | research claim on `envconfig/config.go`; `machines/_defaults.yaml` |

## Common misconceptions and edge cases

- **"A 12 GB model fits on a 12 GB card."** It does not. The weights, the KV cache, working buffers and the Windows
  desktop (about 1.1 GB here) share the card. Leave a margin and read `ollama ps`.
- **"More parameters is always better."** For one user the memory budget and speed decide what is usable. The research
  notes judged the 27B dense models unusable on this card and estimate about 2 tok/s once offloaded (an estimate, not
  measured here).
- **"MoE models are small."** Their per-token cost is small. Their storage is not: the 35B file is 22-23 GB.
- **"Quantized equals the benchmark score."** Vendor scores are full-precision, from the vendor's own setup. The
  research notes say third-party reruns can score far below vendor numbers (one Terminal-Bench 2.0 rerun
  got about 24.6 % against the vendor's 51.5) and Q4 adds more loss. Treat headline numbers as
  upper bounds.
- **Disputed: 39-47 tok/s for the 35B on a 3060.** The research rated this "high" confidence; the verifiers marked it
  contested. They found the flags real but could not open the cited recipe, and the one 3060 benchmark they found
  measured prefill, not decode. On this machine the measured figure is about 25 tok/s on DDR4-2133. Do not quote
  39-47 as a result for this hardware.
- **Corrected: "Ollama cannot offload experts."** True of the old engine; not true of 0.40 with `llama-server` (see
  above). The remaining caveat is that the manual override rides on undocumented pass-through.
- **Changing `num_ctx` is not free.** It forces a reload, and two aliases of one model with different values reload
  against each other.
- **mmap is not "always good".** It avoids the anonymous-memory trap, but evicted file-backed pages are re-read from
  slow storage, so a memory-starved machine still stutters.
- **Free RAM versus "available" RAM.** Cached pages count as available but can be evicted; the benchmark table lists
  "RAM available while loaded" for that reason.
- **Parallel requests cost memory.** `OLLAMA_NUM_PARALLEL` above 1 multiplies the KV cache by the slot count.
- **Speed tricks may not help.** The research notes advise benchmarking speculative decoding first (an Ampere test
  with a small draft model ran slower). The project has not adopted it.
- **Agents can fail before the context limit.** The research notes record a Qwen3.6 chat-template issue where earlier
  "thinking" blocks were dropped unless a flag was set (medium confidence; not verified here).

## How the project uses it

- **Hardware classes.** [`machines/_defaults.yaml`](../../machines/_defaults.yaml) maps VRAM and RAM to a class
  (`moe-12gb-32ram`, `dense-12gb-16ram` and others). Each class names models and sets `primary_num_ctx`,
  `small_num_ctx` and `max_loaded_models`. `uv run scripts/stack.py doctor --write-profile` detects the machine.
- **This machine.** `machines/<HOST>.yaml` overrides the class: `primary:
  qwen3.5:9b`, `primary_options: {}` (no `use_mmap`), and both `primary_num_ctx` and `small_num_ctx` at 32768. Its
  comment gives the reason: 9B at about 52 tok/s with about 18 GB of RAM left, against 35B at about 25 tok/s with
  about 1 GB left. Deleting the four override lines returns to the 35B MoE.
- **Gateway aliases.** In the generated `infrastructure/litellm/config.yaml` (never edit by hand), `local-primary` and
  `local-small` both serve `qwen3.5:9b` at 32768, so all eight 9B deployments share one runner. `local-fim` points to
  `qwen2.5-coder:1.5b-base` with `keep_alive: -1` and a 4,096-token input limit. `local-embed` uses
  `nomic-embed-text`. `local-reviewer` points to `flint:40b-a2b`, which is not pulled.
- **Ollama environment.** `ollama_env` in `_defaults.yaml` sets `OLLAMA_FLASH_ATTENTION=1`,
  `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_QUEUE=32`, `OLLAMA_KEEP_ALIVE=30m`,
  `OLLAMA_GPU_OVERHEAD=536870912` (512 MiB) and `OLLAMA_LOAD_TIMEOUT=15m`. `OLLAMA_MAX_LOADED_MODELS` and
  `OLLAMA_CONTEXT_LENGTH` come from the class. The machine file adds `OLLAMA_MODELS`. `LLAMA_ARG_N_CPU_MOE` is
  commented out as an optional override.
- **The `moe-12gb-32ram` class** sends `use_mmap: true` through `primary_options` and `reviewer_options`.
- **Tooling.** `uv run scripts/stack.py bench` (code in `scripts/stacklib/ollama.py`) loads a model, generates, and
  reports load time, prefill and decode tok/s and the GPU/CPU split from Ollama's `/api/ps`. `--use-mmap` and
  `--num-ctx` let you test variants.
- **Simplifications.** The project runs one engine (Ollama), not `llama-server` directly, to keep one port and one
  model store. It does not use Docker or WSL2 on this machine, so no VM takes RAM from the experts. It skips
  speculative decoding and does not tune `n-cpu-moe` by hand. See
  [`../decisions/2026-10-24-ollama-only-inference.md`](../decisions/2026-10-24-ollama-only-inference.md), the running
  log [`../design/DECISIONS.md`](../design/DECISIONS.md), and section 6 of
  [`../ORCHESTRATOR-DESIGN.md`](../ORCHESTRATOR-DESIGN.md) for the memory budget.

Note: the design document's section 5 and 6 tables still show the 35B MoE as `local-primary` at 32k and the 9B at
16k; the 2026-10-25 override in the machine file is the current state on this machine.

## What we found

Figures are from [`memory/state.md`](../../memory/state.md) (Benchmarks, 2026-10-25, `stack.py bench`, 256 generated
tokens, a 54-token prompt) unless stated.

| model | num_ctx | placement | cold load | warm decode | warm prefill | RAM available while loaded |
|---|---|---|---|---|---|---|
| qwen3.6:35b-a3b-coding, `use_mmap` | 32768 | all 42 layers on GPU; experts of 28 layers in mapped RAM (about 12.7 GB) | 331 s | about 25 tok/s | 183-462 tok/s (noisy) | about 1 GB |
| qwen3.5:9b | 16384 | 100% GPU | 161 s | 51-52 tok/s | 865-927 tok/s | about 17.9 GB |
| qwen3.5:9b via gateway, as primary | 32768 | 100% GPU | 130 s | not measured | not measured | about 17 GB |

What this means:

- The dense 9B decodes about twice as fast as the 35B MoE and leaves about 17 GB of RAM free instead of about 1 GB.
  The first reply after loading the 35B ran at 2.6 tok/s while pages faulted in, and Windows paged at about 110
  pages per second.
- Without mmap, the 35B load hit the five-minute timeout (HTTP 500). `use_mmap: true` plus the 15-minute timeout fixed it.
- The community figure of 39-47 tok/s was not reached. DDR4-2133 and desktop memory pressure are the likely causes;
  not yet tried are `LLAMA_ARG_N_CPU_MOE` tuning, closing apps and faster RAM.
- Smoke runs: with the 9B as primary, `stack.py smoke --dept docs` passed 8 of 8 in 71 s warm (2026-10-25 evening),
  chat reply 2.8 s. With the 35B it passed 8 of 8 in 153 s (2026-10-25 afternoon), chat reply 28.6 s for 141 tokens.
  After the private-only merge (2026-10-26), a full smoke passed 6 of 7 in 28 minutes because the first requests
  queued behind warm-up (first chat 448 s); a warm run passed 8 of 8 in 72 s. Direct Ollama measured 80 tok/s on that
  run (the note does not say which model).
- Lessons in [`memory/lessons.md`](../../memory/lessons.md): RAM pressure, not VRAM, is the binding limit on this
  box; aliases that share a model need equal `num_ctx` and load options.

## Open questions

- Which change would raise the 35B's decode speed here: `LLAMA_ARG_N_CPU_MOE` tuning, closing apps, or faster RAM?
  Not yet tried ([`memory/state.md`](../../memory/state.md), Benchmarks).
- Is the 35B worth switching back to after a RAM upgrade (open item 6 in `memory/state.md`)?
- Why does Ollama disable mmap on Windows with CUDA? The lesson names the source file, but the reason is not recorded.
- How well does the 9B at 32k hold up as `local-primary` in real Claude Code sessions? Profile B has not been run
  live (open item 5).
- Will Ollama's undocumented pass-through of `LLAMA_ARG_N_CPU_MOE` survive future versions? The decision record names
  this as a risk.
- Exact KV bytes per token for Qwen3.5-9B: the research notes infer them; `ollama show <model>` would confirm the
  layer count, KV heads and head dimension.
- Independent (non-vendor) coding scores for these models at Q4: the research notes say none were found.
- The real bits per weight of each Q4 scheme in the files used: source not recorded.

## Sources and further reading

| Source | Author / year | Good for |
|---|---|---|
| [research-local-models.json](../research/research-local-models.json) | project research, 2026-10-24 | model lineup, KV cost, FIM choices, caveats |
| [research-inference-engine.json](../research/research-inference-engine.json) | project research, 2026-10-24 | Ollama settings, scheduler behaviour, KV maths |
| [verification-status.json](../research/verification-status.json) | project verification, 2026-10 | which claims held, were contested or refuted |
| [memory/state.md](../../memory/state.md), [memory/lessons.md](../../memory/lessons.md) | project, 2026-10 | machine facts, measurements, lessons |
| [ORCHESTRATOR-DESIGN.md](../ORCHESTRATOR-DESIGN.md) sections 5-6 | project, 2026 | bandwidth tiers and memory budget |
| [Ollama FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx) | Ollama, 2026 | flash attention and KV cache quantization |
| [Ollama on Windows](https://github.com/ollama/ollama/blob/main/docs/windows.mdx) | Ollama, 2026 | native Windows install, env vars, logs |
| [Ollama envconfig/config.go](https://raw.githubusercontent.com/ollama/ollama/main/envconfig/config.go) | Ollama, 2026 | defaults of every `OLLAMA_*` variable |
| [Ollama server/sched.go](https://raw.githubusercontent.com/ollama/ollama/main/server/sched.go) | Ollama, 2026 | runner sharing, eviction, reload rules |
| [Ollama llm/llama_server.go](https://raw.githubusercontent.com/ollama/ollama/main/llm/llama_server.go) | Ollama, 2026 | parallel slots and the request queue |
| [llama.cpp server README](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/README.md) | ggml-org, 2026 | `--n-cpu-moe`, `-ngl`, cache types, `-np` |
| [Ollama PR 12333](https://github.com/ollama/ollama/pull/12333) | Ollama contributors | the unmerged expert-offload proposal |
| [Qwen3.6-35B-A3B announcement](https://qwen.ai/blog?id=qwen3.6-35b-a3b) | Qwen team, 2026 | model design (35B total, 3B active) |
| [Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B) | Qwen team, 2026 | the 9B's design and context length |
| [Continue autocomplete guide](https://docs.continue.dev/customize/deep-dives/autocomplete) | Continue, 2026 | FIM model choices |
| [Qwen3.6-35B on RTX 3060 recipe](https://smeltcore.com/recipes/qwen3-6-35b-a3b-on-rtx-3060-38-9-tok-s-from-a-12gb-card-via-moe-expert-cpu-offload/) | smeltcore, 2026 | community expert-offload flags; speed claim contested |
| [gpt-oss model card](https://arxiv.org/pdf/2508.10925) | OpenAI, 2025 | a second MoE example (21B total, about 3.6B active) |

## Changes

2026-11-01: first version.
