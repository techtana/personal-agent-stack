# Ollama is the only local inference engine (no separate llama-server)

- Status: accepted (2026-10-24)
- Context: the research recommended llama.cpp `llama-server --n-cpu-moe` for the MoE tier because Ollama was
  believed to lack expert-aware offload. The on-prem verification (and the cloud session's late recency check)
  showed Ollama >= 0.30 runs every GGUF through upstream `llama-server` with `LLAMA_ARG_FIT=on`, whose fit step
  places MoE experts on the CPU automatically, and passes `LLAMA_ARG_N_CPU_MOE` through as a manual override.
- Decision: one engine. The hardware class decides the model; `stack.py bench` measures tok/s and the GPU/CPU
  split; the manual override lives in `machines/<host>.yaml:ollama_env` if the automatic fit is poor.
- Consequences: simpler stack (one port, one model store, Open WebUI/LiteLLM/Claude Code all speak to :11434);
  the trade-off is depending on Ollama's undocumented pass-through for manual tuning.
