# Run every service natively on the GPU workstation; keep Docker optional

- Status: accepted (2026-10-24)
- Context: the handoff assumed Docker Desktop + WSL2 and an existing Ollama/Open WebUI. The machine had none
  of them. WSL2 reserves system RAM for its VM, and the primary local model (Qwen3.6-35B-A3B, MoE) keeps its
  expert weights in system RAM; on a 32 GB box that RAM is the scarce resource.
- Options: (A) install Docker Desktop and run LiteLLM/Phoenix/Open WebUI in containers with native Ollama;
  (B) run everything as native processes managed by `scripts/stack.py` (uv tools + Ollama app);
  (C) run Ollama in a container too (rejected by the research: GPU passthrough flakiness, port collision).
- Decision: B. Compose remains in `infrastructure/docker-compose.yml` for Linux servers, untested here.
- Consequences: no container isolation between services; process management is a small custom module
  (`scripts/stacklib/services.py`, pid files + health URLs); upgrades are `uv tool install --force`.
