export const meta = {
  name: 'review-and-research-agent-stack',
  description: 'Critique existing Deep-Architect plan + stack, research Oct-2026 best practice for local agent orchestration, verify key claims, write review doc',
  phases: [
    { title: 'Critique', detail: 'parallel readers over the existing design + implementation' },
    { title: 'Research', detail: 'parallel web researchers, one per topic' },
    { title: 'Verify', detail: '3-lens adversarial verification of load-bearing claims' },
    { title: 'Synthesize', detail: 'write docs/REVIEW-2026-10.md and run a completeness critic' },
  ],
}

const CONTEXT = [
  'PROJECT CONTEXT (read carefully, it is authoritative):',
  '- Repo: /home/user/personal-agent-stack (git, branch claude/local-coding-agents-setup-U45yO). Today is 2026-10-24.',
  '- Owner goal: a professional LOCAL coding-agent stack with department agents (app-dev, testing, security, devops, code-review, docs).',
  '  Local open-source models handle cheap/simple work; Claude or other cloud providers handle heavy work.',
  '  Hard requirements from the owner: (1) right tool for the right bandwidth tier, (2) the system is SELF-DEVELOPING,',
  '  i.e. it improves its own prompts/routing/skills from experience, (3) cost is minimized, (4) it is INTUITIVE to interact with,',
  '  (5) it may compose multiple open-source tools rather than one custom monolith.',
  '- Hardware per docs/DESIGN.md: NVIDIA RTX 3060 12GB VRAM, Windows 11 host. Assume 32-64GB system RAM unless evidence says otherwise.',
  '  Owner already has: Ollama, Docker (Desktop), Open WebUI, VS Code. They use Claude Code too.',
  '- What exists today: docs/DESIGN.md (an older plan for a custom VS Code extension "Deep-Architect": 4-phase FSM, 9-hour autonomous',
  '  sessions, Python RAG sidecar, circuit breaker, thermal gating, AGENTS.md as persisted state). Plus a stack built last session:',
  '  router/main.py (FastAPI OpenAI-compatible proxy doing keyword+length complexity routing local vs cloud), router/agents.yaml',
  '  (6 agents with system prompts), config/ollama/Modelfile.* (same prompts baked into Ollama models), infrastructure/docker-compose.yml',
  '  (ollama + router + open-webui), scripts/*.sh, config/vscode/continue.config.json, README.md.',
  '- Authoritative current Anthropic model IDs (from the runtime environment, trust these over web memory): claude-fable-5-1 (Fable 5.1),',
  '  claude-opus-5-5 (Opus 5.5), claude-sonnet-5-5 (Sonnet 5.5), claude-haiku-4-5-20251001 (Haiku 4.5). The repo currently references',
  '  claude-sonnet-4-6 and claude-opus-4-8 — treat those as suspect/stale.',
  '- Your final text IS the return value consumed by a script, not a chat message. Return exactly the structured output requested.',
].join('\n')

const CRITIQUE_SCHEMA = {
  type: 'object',
  properties: {
    area: { type: 'string' },
    summary: { type: 'string', description: '3-5 sentence overall assessment' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          file: { type: 'string' },
          detail: { type: 'string' },
          recommendation: { type: 'string' },
        },
        required: ['title', 'severity', 'detail', 'recommendation'],
      },
    },
    keep: { type: 'array', items: { type: 'string' }, description: 'ideas/components worth keeping and why' },
    replace: { type: 'array', items: { type: 'string' }, description: 'things to replace with an off-the-shelf OSS tool, naming the tool' },
    drop: { type: 'array', items: { type: 'string' } },
  },
  required: ['area', 'summary', 'findings', 'keep', 'replace', 'drop'],
}

const RESEARCH_SCHEMA = {
  type: 'object',
  properties: {
    topic: { type: 'string' },
    summary: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string', description: 'one precise, falsifiable statement' },
          evidence: { type: 'string' },
          source_url: { type: 'string' },
          source_date: { type: 'string', description: 'date of the source if visible, else empty' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
          load_bearing: { type: 'boolean', description: 'true if the recommended architecture would change were this claim false' },
          why_load_bearing: { type: 'string' },
        },
        required: ['claim', 'evidence', 'source_url', 'confidence', 'load_bearing'],
      },
    },
    recommendations: { type: 'array', items: { type: 'string' } },
    open_questions: { type: 'array', items: { type: 'string' } },
  },
  required: ['topic', 'summary', 'findings', 'recommendations', 'open_questions'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    reasoning: { type: 'string' },
    corrected_claim: { type: 'string', description: 'if refuted or imprecise, the accurate version; else empty' },
    source_url: { type: 'string' },
  },
  required: ['refuted', 'confidence', 'reasoning'],
}

const GAPS_SCHEMA = {
  type: 'object',
  properties: {
    gaps: { type: 'array', items: { type: 'object', properties: { gap: { type: 'string' }, why_it_matters: { type: 'string' }, how_to_close: { type: 'string' } }, required: ['gap', 'why_it_matters', 'how_to_close'] } },
    unverified_claims_used_as_fact: { type: 'array', items: { type: 'string' } },
    overall: { type: 'string' },
  },
  required: ['gaps', 'unverified_claims_used_as_fact', 'overall'],
}

const CRITICS = [
  {
    key: 'design-doc',
    prompt: CONTEXT + '\n\nTASK: You are a principal engineer reviewing docs/DESIGN.md (read the whole file, ~500 lines) against October-2026 best practice for coding agents.\n' +
      'The doc proposes building a bespoke VS Code extension with its own 4-phase state machine, Python RAG sidecar (tree-sitter + FAISS), circuit breaker, thermal gating, episodic log, and an AGENTS.md state file.\n' +
      'Judge each major idea: is it still the right call now that Claude Code, OpenCode, Cline/Roo, Aider, Goose etc. already provide agent loops, tool use, subagents, hooks, MCP and AGENTS.md support out of the box? Which ideas are durable and should be ported into a thinner orchestrator (e.g. AGENTS.md persisted state, circuit breaker on repeated tool-call sequences, cloud budget caps, thermal/VRAM awareness, adversarial brainstorm)? Which are reinventing wheels? Are the three "technical unknowns" still unknown? Is a 9-hour autonomous local-model session realistic on a 3060, and what is the realistic alternative (bounded tasks, human-in-the-loop checkpoints)?\n' +
      'Be concrete and opinionated. Cite line numbers from the doc. Output the structured critique.',
  },
  {
    key: 'router-code',
    prompt: CONTEXT + '\n\nTASK: You are a senior backend engineer doing a rigorous code review of router/main.py (373 lines) and router/agents.yaml (306 lines), plus router/Dockerfile and router/requirements.txt. Read every line.\n' +
      'Assess: (a) correctness of the OpenAI-compatible surface (the Message model only allows string content, so tool calls, tool results, images, and OpenAI "content parts" arrays will 422 — verify), streaming SSE format, Anthropic SDK usage, error handling, what happens when Ollama is down (is there a fallback?), timeouts, request size limits, concurrency; (b) the complexity classifier: keyword + len//4 token heuristic — list concrete misroutes it will make (false positives like the word "migrate" in a trivial question; false negatives like a short prompt attached to a huge diff via tool context), and compare with known approaches (LiteLLM router/fallbacks, RouteLLM, cascade with local-first + self-check, architect/editor split); (c) the model IDs referenced (claude-sonnet-4-6, claude-opus-4-8) vs the authoritative IDs in context; (d) duplication: system prompts live in agents.yaml AND config/ollama/Modelfile.* — drift risk; (e) whether this router should exist at all versus LiteLLM proxy + a thin agent-dispatch layer; (f) missing observability: no per-request cost/latency/provider logging, no usage accounting.\n' +
      'Also evaluate the six system prompts for quality: are they too long for a 7B-14B model context budget, do they conflict with how coding agents (Claude Code/OpenCode) already prompt, are the "complexity_keywords" sensible?\n' +
      'Output the structured critique with file:line references.',
  },
  {
    key: 'infra-scripts-readme',
    prompt: CONTEXT + '\n\nTASK: You are an SRE reviewing infrastructure/docker-compose.yml, infrastructure/.env.example, scripts/setup.sh, scripts/pull-models.sh, scripts/create-agents.sh, and README.md. Read all of them fully.\n' +
      'Assess for a Windows 11 + Docker Desktop (WSL2) + RTX 3060 12GB owner who ALREADY runs Ollama natively: (a) running Ollama inside Docker duplicates the native install and model store, and GPU passthrough via WSL2 is slower/flakier than native — should compose point at host.docker.internal:11434 instead? (b) the deprecated top-level "version" key; (c) OLLAMA_MAX_LOADED_MODELS=3 with qwen2.5-coder:14b (~9GB Q4) + deepseek-r1:14b (~9GB) + 7b (~4.7GB) cannot co-reside in 12GB — compute actual VRAM at 16k context with KV cache; (d) healthchecks assume curl exists inside the ollama image (verify); (e) scripts: bash on Windows (Git Bash/WSL?), set -euo pipefail, idempotency, the setup flow stopping to edit .env, no PowerShell equivalent; (f) README accuracy vs the code, missing Windows instructions, missing uninstall, missing cost section accuracy; (g) secrets handling (.env committed? .gitignore ok?); (h) model choices stale — qwen2.5-coder / deepseek-r1 are 2024-2025 era; note what should be re-evaluated (do not research yourself, just flag).\n' +
      'Output the structured critique.',
  },
  {
    key: 'ux-surfaces',
    prompt: CONTEXT + '\n\nTASK: You are a developer-experience lead. Read config/vscode/continue.config.json, all six config/ollama/Modelfile.*, README.md sections about VS Code and Open WebUI usage, and AGENTS.md. Evaluate the stack purely from the owner\'s point of view: "I want to ask the security agent to review this file" or "run the tests and fix failures" — how many different entry points exist (Open WebUI model picker, Continue assistants, raw Ollama agent-* models, Claude Code, router API), do they behave consistently, where does state/memory live, and is any of it actually agentic (can it edit files and run tests) or is it chat-only?\n' +
      'Check the Continue config format: Continue moved to YAML config.yaml (config.json is legacy) — verify and flag. Check whether Modelfile-baked prompts and router-injected prompts double up when Open WebUI talks to agent-* models through Ollama directly. Identify what an INTUITIVE single interaction model would look like for terminal, IDE, and chat (e.g. one CLI verb per department, or one agent that delegates to departments as subagents, with the same AGENTS.md/skills shared by all surfaces).\n' +
      'Output the structured critique, with a concrete proposal for the interaction model in the summary.',
  },
]

const RESEARCHERS = [
  {
    key: 'local-models',
    prompt: CONTEXT + '\n\nRESEARCH TOPIC: Best open-weight coding and agentic models runnable on an RTX 3060 12GB (with CPU/RAM offload for MoE) as of October 2026.\n' +
      'Use web search and fetch primary sources (ollama.com/library pages, Hugging Face model cards, official blogs, llama.cpp discussions, Aider polyglot and SWE-bench leaderboards). Cover at least: Qwen3-Coder family (30B-A3B and any later/smaller releases), Qwen3 dense 8B/14B/32B incl. 2507/2509 refreshes, gpt-oss-20b, Devstral Small 2 / Devstral 2 / Devstral latest, GLM-4.5-Air / GLM-4.6 / later, Gemma 3 12B / 3n, Mistral Small 3.x / Codestral, Nemotron Nano, Seed-OSS, DeepSeek-Coder-V2-Lite and any model released after June 2026 that a 12GB card can run. Also small FIM/autocomplete models (qwen2.5-coder:1.5b/3b, qwen3-coder small variants, starcoder2).\n' +
      'For each model report: total/active params, exact Ollama tag if it exists (verify the tag on ollama.com/library), GGUF size at Q4_K_M, estimated VRAM at 16k and 32k context (state KV cache assumptions), tool-calling reliability in agent loops, benchmark scores you can source, approximate tok/s on 3060-class hardware if reported. Note which MoE models run acceptably with partial CPU offload on 12GB (only ~3B active) and the tok/s penalty.\n' +
      'Recommend a 3-tier local lineup: (1) autocomplete/FIM, (2) workhorse chat+agent, (3) local-heavy reasoning/review; plus one stretch option. Mark load_bearing claims (e.g. "model X fits in 12GB at Q4 with 32k ctx", "Ollama tag Y exists").',
  },
  {
    key: 'agent-frontends',
    prompt: CONTEXT + '\n\nRESEARCH TOPIC: Open-source agentic coding frontends (terminal, IDE, web) that can mix local Ollama/llama.cpp/LiteLLM models with cloud models, as of October 2026, and which are the most intuitive to live in daily.\n' +
      'Cover: OpenCode (sst/opencode), Crush (charmbracelet), Aider (incl. architect/editor mode and weak-model settings), Cline, Roo Code, Kilo Code, Continue (incl. its 2025-2026 config.yaml and "agents" concept), Goose (Block), OpenHands, Zed agent panel, Claude Code (closed source but central to the owner), OpenAI Codex CLI (open source; --oss / Ollama support), Gemini CLI, Qwen Code. Also Open WebUI as a chat surface: Workspace models, Tools, Pipelines/Functions, native MCP support or mcpo, Channels, Notes.\n' +
      'For each: license, maturity/activity, how to point it at Ollama and at an OpenAI/Anthropic-compatible proxy, MCP client support, subagent/multi-agent support, per-task or per-mode model selection (e.g. plan vs build vs cheap), AGENTS.md support, session persistence, UX type. Fetch official docs for provider configuration and include exact config snippets where possible.\n' +
      'Recommend: primary terminal surface, primary IDE surface, primary chat surface, and how one shared set of agent definitions could be reused across them. Mark load_bearing claims.',
  },
  {
    key: 'claude-code-local',
    prompt: CONTEXT + '\n\nRESEARCH TOPIC: Exact current mechanisms (October 2026) to run Claude Code against local or alternative models, and Claude Code features relevant to a multi-department orchestrator.\n' +
      'Investigate with primary sources (docs.claude.com / code.claude.com, Ollama blog and docs, LiteLLM docs, GitHub repos): (1) ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN pointed at a LiteLLM proxy exposing /v1/messages; (2) Ollama native Anthropic Messages API compatibility — which Ollama version added it, exact env vars (ANTHROPIC_BASE_URL=http://localhost:11434, ANTHROPIC_API_KEY/AUTH_TOKEN values), which models work with tool calling, known limitations; (3) claude-code-router (musistudio) and similar routers; (4) ANTHROPIC_MODEL, ANTHROPIC_SMALL_FAST_MODEL, ANTHROPIC_DEFAULT_OPUS_MODEL/SONNET/HAIKU env vars and CLAUDE_CODE_SUBAGENT_MODEL; (5) Claude Code subagents (.claude/agents/*.md frontmatter: name, description, tools, model, permissionMode), skills (.claude/skills/*/SKILL.md), hooks (PreToolUse/PostToolUse/Stop/SessionStart etc.), MCP config (.mcp.json), agent teams, output styles, --agent flag, /agents; (6) Claude Code OpenTelemetry/cost env vars; (7) economics: Claude Max subscription vs API key for Claude Code and whether subscription auth can be routed through a proxy (likely no — verify).\n' +
      'Provide verified config snippets. Mark load_bearing claims (especially: Ollama /v1/messages support and version; whether subagent "model" can name an Ollama model via ANTHROPIC_BASE_URL).',
  },
  {
    key: 'routing-proxy',
    prompt: CONTEXT + '\n\nRESEARCH TOPIC: The gateway/routing layer for a mixed local+cloud stack, October 2026 — how to minimize cost while keeping quality.\n' +
      'Investigate LiteLLM proxy in depth from docs.litellm.ai and the GitHub repo: model_list with ollama/ and ollama_chat/ and anthropic/ providers, model aliases/groups, router_settings (fallbacks, context_window_fallbacks, routing strategies incl. cost-based and latency-based), budgets/virtual keys/spend tracking DB requirements, /v1/messages (Anthropic format) support and Anthropic passthrough, pre-call hooks / custom routing strategy (CustomLogger async_pre_call_hook) to implement complexity routing, prompt caching passthrough for Anthropic, Redis caching, Langfuse/OTel/Prometheus callbacks, current docker image tag and a minimal config.yaml. Then alternatives: RouteLLM (strong/weak routers, how to self-host), semantic-router (aurelio), Portkey Gateway OSS, Bifrost, Kong AI gateway, Arch gateway (katanemo), Ollama built-in capabilities. Also patterns: cascade (local answers, local or cheap judge grades, escalate on low confidence), architect/editor split (cloud plans, local edits), speculative/parallel race, and "cheap first draft then cloud review".\n' +
      'Recommend the routing architecture: which component decides local vs cloud, with what signals (task type, context size, tool-loop depth, prior failure count, user override), and how it stays tunable. Mark load_bearing claims (e.g. LiteLLM supports /v1/messages with tool calling to Ollama models; custom pre-call hook can rewrite model).',
  },
  {
    key: 'self-improving',
    prompt: CONTEXT + '\n\nRESEARCH TOPIC: Practical "self-developing" mechanisms for a personal coding-agent stack in October 2026 — how the system can improve its own prompts, routing, skills and memory from experience, using open-source tools, with a human approving changes.\n' +
      'Investigate: Claude Code Skills (SKILL.md format, progressive disclosure, skill-creator), the agents.md convention (agents.md spec, which tools read it), memory systems (mem0 OSS, Letta/MemGPT, Claude Code auto-memory, simple git-committed markdown memory), trace-driven prompt optimization (DSPy GEPA / MIPROv2 with local judges), Karpathy-style "autoresearch" loops, nightly retrospective agents that read traces and open PRs with proposed prompt/routing changes, eval harnesses to gate changes (promptfoo, Inspect, lm-eval-harness, Aider polyglot subset, SWE-bench Lite/Verified subsets, terminal-bench), feedback capture (Open WebUI thumbs, Claude Code hooks recording test pass/fail and tool-loop length), and model promotion/demotion based on eval results. Find at least two real open-source projects or write-ups implementing a closed loop like this and describe their design.\n' +
      'Recommend a concrete minimal loop (data captured -> nightly analysis by local model -> proposed diff to skills/prompts/routing -> eval gate -> human approves PR). Mark load_bearing claims.',
  },
  {
    key: 'observability-cost',
    prompt: CONTEXT + '\n\nRESEARCH TOPIC: Observability and cost control for a mixed local/cloud LLM stack on a single workstation, October 2026 — the lightest setup that yields per-agent cost, latency, and quality signals.\n' +
      'Investigate: Langfuse self-hosted (v3 docker compose requirements: Postgres, ClickHouse, Redis, MinIO — RAM footprint), lighter alternatives (Arize Phoenix single container, Comet Opik, Helicone OSS, Lunary, LiteLLM built-in spend logs + Prometheus/Grafana), OpenTelemetry GenAI semantic conventions and which tools emit/ingest them, Open WebUI to Langfuse pipeline/filter, Claude Code OTel export env vars (CLAUDE_CODE_ENABLE_TELEMETRY, OTEL_* ) and what metrics it exposes (cost, tokens, tool usage), Anthropic prompt caching and Batch API price reductions, Claude Max/Pro subscription vs API economics for heavy daily agent use, and simple cost dashboards. Also local-side signals: tok/s, VRAM, GPU temp via nvidia-smi/DCGM exporter.\n' +
      'Recommend the lightest stack giving per-department cost + quality signals and feeding the self-improvement loop. Mark load_bearing claims.',
  },
  {
    key: 'inference-engine',
    prompt: CONTEXT + '\n\nRESEARCH TOPIC: Inference engine and settings for one RTX 3060 12GB on Windows 11 (Docker Desktop/WSL2 available), October 2026.\n' +
      'Investigate Ollama latest (version, new engine, tool calling and structured outputs, OLLAMA_FLASH_ATTENTION, OLLAMA_KV_CACHE_TYPE q8_0/q4_0, OLLAMA_NUM_PARALLEL and how concurrent requests are queued, OLLAMA_MAX_LOADED_MODELS, context length config, Anthropic-compatible API, Ollama cloud models, Modelfile vs API-time system prompts, Windows native install vs Docker+WSL2 GPU passthrough performance/flakiness), llama.cpp llama-server (speculative decoding with draft models, --fit / auto GPU layer fit, router/multi-model mode, Windows CUDA builds), vLLM (why it is a poor fit for 12GB), LM Studio and Jan (OpenAI-compatible servers, MLX/CUDA), TabbyAPI/exllamav3, SGLang. Compute KV-cache memory for typical models (e.g. Qwen3-14B, Qwen3-Coder-30B-A3B, gpt-oss-20b) at 16k/32k context with q8_0 cache to say what actually fits in 12GB alongside weights. Report what happens when two agents hit Ollama simultaneously and how to serialize or parallelize safely.\n' +
      'Recommend engine + exact settings (env vars) and a model-residency plan (which models stay loaded, keep_alive). Mark load_bearing claims.',
  },
  {
    key: 'mcp-tools',
    prompt: CONTEXT + '\n\nRESEARCH TOPIC: MCP and tool ecosystem for department coding agents, October 2026.\n' +
      'Investigate: the official MCP registry and spec status (versions, auth, streamable HTTP), the essential servers for coding (filesystem, git, github official, playwright, context7 docs, serena / LSP-based semantic tools, memory, fetch, sequential-thinking, sqlite/postgres), security findings (tool poisoning, prompt injection via tool output, rug pulls; mitigations like allowlists and read-only modes), the pattern of exposing an orchestrator itself as an MCP server with a delegate(department, task) tool so any client (Claude Code, OpenCode, Open WebUI) can dispatch work to department agents, Open WebUI MCP support (native vs mcpo), A2A protocol status and whether it matters for a single-user stack, and how Claude Code/OpenCode/Continue each configure MCP servers (file formats).\n' +
      'Recommend a minimal MCP toolset per department (app-dev, testing, security, devops, code-review, docs) and the config files to ship. Mark load_bearing claims.',
  },
]

phase('Critique')
log('Running ' + CRITICS.length + ' critics and ' + RESEARCHERS.length + ' researchers concurrently')

const [critiques, research] = await parallel([
  () => parallel(CRITICS.map(c => () => agent(c.prompt, { label: 'critique:' + c.key, phase: 'Critique', schema: CRITIQUE_SCHEMA, effort: 'high' }))),
  () => parallel(RESEARCHERS.map(r => () => agent(r.prompt, { label: 'research:' + r.key, phase: 'Research', schema: RESEARCH_SCHEMA, effort: 'high' }))),
])

const crit = critiques.filter(Boolean)
const res = research.filter(Boolean)
log('Critiques: ' + crit.length + '/' + CRITICS.length + ', research topics: ' + res.length + '/' + RESEARCHERS.length)

phase('Verify')
const allClaims = res.flatMap(r => (r.findings || []).map(f => ({ ...f, topic: r.topic })))
const lb = allClaims.filter(f => f.load_bearing)
const seen = new Set()
const uniq = []
for (const c of lb) {
  const k = (c.claim || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().slice(0, 80)
  if (!k || seen.has(k)) continue
  seen.add(k)
  uniq.push(c)
}
const CAP = 24
const toVerify = uniq.slice(0, CAP)
log('Load-bearing claims: ' + lb.length + ' (' + uniq.length + ' unique). Verifying ' + toVerify.length + (uniq.length > CAP ? ' — DROPPED ' + (uniq.length - CAP) + ' beyond cap' : ''))

const LENSES = [
  { key: 'source', instr: 'LENS = PRIMARY SOURCE. Find the primary source (official docs, repo, release notes, model card). Refute if the claim is not actually supported by a primary source or misstates numbers/versions. Default refuted=true if you cannot find support.' },
  { key: 'recency', instr: 'LENS = RECENCY. Check whether the claim has been superseded, deprecated, renamed, or changed as of October 2026 (new versions, renamed env vars, new model releases, deprecated config formats). Refute if outdated. Default refuted=true if you cannot establish it is still current.' },
  { key: 'practitioner', instr: 'LENS = PRACTITIONER. Would this actually work on the stated hardware/OS (RTX 3060 12GB, Windows 11, Docker Desktop/WSL2) for a single developer? Check VRAM math, Windows caveats, known issues in GitHub issues. Refute if impractical or if the claim hides a serious caveat.' },
]

const verified = await pipeline(
  toVerify,
  (c, _item, i) => parallel(LENSES.map(l => () => agent(
    CONTEXT + '\n\nYou are an adversarial fact-checker. Try hard to REFUTE the following claim; do not be charitable.\n' + l.instr +
    '\n\nCLAIM: ' + c.claim + '\nEVIDENCE GIVEN: ' + c.evidence + '\nSOURCE GIVEN: ' + (c.source_url || 'none') + '\nTOPIC: ' + c.topic +
    '\n\nUse web search/fetch. Return the structured verdict with a URL you actually opened.',
    { label: 'verify:' + (i + 1) + ':' + l.key, phase: 'Verify', schema: VERDICT_SCHEMA }
  ))).then(votes => {
    const vs = votes.filter(Boolean)
    const refutes = vs.filter(v => v.refuted).length
    const corrected = vs.map(v => v.corrected_claim).filter(Boolean)
    return { ...c, votes: vs, refuted: vs.length > 0 && refutes * 2 >= vs.length + 1 ? true : refutes * 2 > vs.length, refute_count: refutes, vote_count: vs.length, corrections: corrected }
  })
)

const vOk = verified.filter(Boolean)
const confirmed = vOk.filter(v => !v.refuted)
const refuted = vOk.filter(v => v.refuted)
log('Verified: ' + confirmed.length + ' confirmed, ' + refuted.length + ' refuted')

phase('Synthesize')
const synthInput = {
  critiques: crit,
  research_summaries: res.map(r => ({ topic: r.topic, summary: r.summary, recommendations: r.recommendations, open_questions: r.open_questions, non_load_bearing_findings: (r.findings || []).filter(f => !f.load_bearing).map(f => ({ claim: f.claim, source_url: f.source_url, confidence: f.confidence })) })),
  confirmed_claims: confirmed.map(v => ({ claim: v.claim, source_url: v.source_url, corrections: v.corrections, topic: v.topic })),
  refuted_claims: refuted.map(v => ({ claim: v.claim, corrections: v.corrections, reasoning: v.votes.map(x => x.reasoning), topic: v.topic })),
  unverified_load_bearing: uniq.slice(CAP).map(c => c.claim),
}

const synthSummary = await agent(
  CONTEXT + '\n\nTASK: You are the lead architect. Using ONLY the material below, write the file /home/user/personal-agent-stack/docs/REVIEW-2026-10.md (create it; overwrite if present) and then return a 15-line plain-text summary of its key decisions.\n' +
  'Rules: (1) Treat confirmed_claims as fact and cite their URLs inline. (2) Where a refuted claim appears, state the corrected version and mark it "(corrected)". (3) Anything from research_summaries that was not verified must be labelled "(unverified)". (4) Do not invent sources. (5) Use the authoritative Anthropic model IDs from context. (6) Be opinionated and concrete; this doc drives implementation next.\n' +
  'Required sections, in order:\n' +
  '1. Executive summary (10 lines max).\n' +
  '2. What the old plan (docs/DESIGN.md) got right — durable ideas to port.\n' +
  '3. Decision table: every major element of the old plan AND of the current stack (router, Modelfiles, Continue json, compose, scripts) -> KEEP / REPLACE WITH <oss tool> / DROP, with one-line rationale.\n' +
  '4. Current best-known methods by area (models for 12GB, frontends, Claude Code + local, gateway/routing, self-improvement loop, observability/cost, inference engine + settings, MCP) — each with verified facts cited and a crisp recommendation.\n' +
  '5. Recommended target architecture: an ASCII diagram plus a narrative mapping the owner\'s four requirements (bandwidth tiers, self-developing, min cost, intuitive) to components. Define the bandwidth tiers explicitly (T0 autocomplete, T1 local chat/edit, T2 local agentic, T3 cloud agentic, T4 cloud heavy reasoning) with the signals that move a task between tiers.\n' +
  '6. Model lineup for RTX 3060 12GB with VRAM math (only verified numbers; label estimates).\n' +
  '7. Interaction model: exactly how the owner invokes each department from terminal, IDE, and chat, and where shared state (AGENTS.md, skills, memory) lives.\n' +
  '8. Self-improvement loop: data captured -> analysis -> proposed change -> eval gate -> human approval, with the OSS tools named.\n' +
  '9. Cost plan: what stays free/local, what hits cloud, caps and tracking.\n' +
  '10. Open questions and unverified items.\n' +
  'Write the file with the Write tool, then return the 15-line summary as your final text.\n\nMATERIAL (JSON):\n' + JSON.stringify(synthInput, null, 1),
  { label: 'synthesize:review-doc', phase: 'Synthesize', effort: 'xhigh' }
)

const gaps = await agent(
  CONTEXT + '\n\nTASK: Completeness critic. Read /home/user/personal-agent-stack/docs/REVIEW-2026-10.md in full. Then compare against the raw material (JSON below) and the owner\'s four requirements. Ask: what is missing (a modality not covered, a requirement not mapped to a component, a decision without rationale, Windows-specific gaps, security of the orchestrator itself, backup/restore of state, offline operation, multi-project use)? Which statements in the doc are presented as fact but appear in refuted_claims or were never verified? Return the structured gaps list.\n\nMATERIAL (JSON):\n' + JSON.stringify({ confirmed: synthInput.confirmed_claims.map(c => c.claim), refuted: synthInput.refuted_claims.map(c => c.claim), unverified: synthInput.unverified_load_bearing }, null, 1),
  { label: 'critic:completeness', phase: 'Synthesize', schema: GAPS_SCHEMA, effort: 'high' }
)

return {
  doc: 'docs/REVIEW-2026-10.md',
  synth_summary: synthSummary,
  critique_summaries: crit.map(c => ({ area: c.area, summary: c.summary, critical_high: (c.findings || []).filter(f => f.severity === 'critical' || f.severity === 'high').map(f => f.title), replace: c.replace, drop: c.drop })),
  research_recommendations: res.map(r => ({ topic: r.topic, recommendations: r.recommendations })),
  confirmed_count: confirmed.length,
  refuted: refuted.map(v => ({ claim: v.claim, corrections: v.corrections })),
  dropped_unverified: uniq.length > CAP ? uniq.length - CAP : 0,
  gaps,
}