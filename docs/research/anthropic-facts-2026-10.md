# Authoritative Anthropic facts (claude-api skill, cached 2026-10-06; verified in-session 2026-10-24)

## Model IDs and list prices ($ per MTok input / output; cache read)
- claude-fable-5-1   Fable 5.1   $10 / $50   (cache read $0.25)  1M ctx, 128K out. Thinking always on; effort low..max.
- claude-opus-5-5    Opus 5.5    $4  / $20   (cache read $0.20)  1M ctx. Thinking cannot be disabled; effort default MEDIUM.
- claude-sonnet-5-5  Sonnet 5.5  $2  / $10   (cache read $0.20)  1M ctx. Effort default high; `between_tools` to turn thinking off.
- claude-haiku-5-5   Haiku 5.5   $0.10 / $0.50 (<=100K prompt; $0.50/$2.50 beyond). 1M ctx. Effort default medium.
- Older still served: claude-opus-4-8 ($5/$25), claude-sonnet-4-6 ($3/$15), claude-haiku-4-5 ($1/$5, 200K).
  -> repo's current IDs (sonnet-4-6, opus-4-8) are real but previous-gen and MORE expensive than 5.5 tier.

## API behaviours that affect a proxy/router
- Since 2026-10-21: temperature/top_p/top_k => HTTP 400 on EVERY model. Router must strip them for Anthropic.
- Forced tool_choice any/tool => 400 on Fable 5.1 / Opus 5.5 / Sonnet 5.5. Use auto + strict:true.
- Assistant prefill => 400 on all current models.
- thinking: {type:"adaptive"} or omit; budget_tokens => 400 on 5.x.
- output_config.effort: low|medium|high|xhigh|max — the primary cost lever within a model.
- Prompt caching: prefix match, up to 4 breakpoints, min cacheable prefix 512-4096 tok; verify via usage.cache_read_input_tokens.
- Mid-conversation system messages (role:"system" inside messages[]) preserve cache prefix on 5.x.
- Batch API: 50% off, async — good for nightly retrospective / eval jobs.
- Server-side fallbacks beta for refusals: betas:["server-side-fallback-2026-07-01"], fallbacks:"default".
- Auth: ANTHROPIC_API_KEY -> ANTHROPIC_AUTH_TOKEN -> `ant auth login` OAuth profile. Claude Code uses ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN for proxies.
- Guidance: measure "most capable model at LOWER effort" before building a multi-model cascade; caches are model-scoped.
