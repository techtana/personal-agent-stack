# Personal Agent Stack

A local-first multi-agent coding infrastructure with automatic cloud fallback.
Six specialized agents handle distinct phases of software development, running on local models for speed and cost, escalating to Claude API only when complexity demands it.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  VS Code (Continue ext)     Open WebUI                  │
│         │                        │                      │
└─────────┼────────────────────────┼──────────────────────┘
          │ OpenAI-compatible API  │
          ▼                        ▼
┌──────────────────────────────────────────────────────────┐
│                   Agent Router :8000                     │
│                                                          │
│  ┌─────────────┐   ┌──────────────────────────────────┐ │
│  │ Complexity  │   │  System Prompt Injector          │ │
│  │ Classifier  │   │  (bakes agent persona per model) │ │
│  └──────┬──────┘   └──────────────────────────────────┘ │
│         │                                               │
│    local │ cloud                                        │
│         ▼         ▼                                     │
└─────────┼─────────┼────────────────────────────────────┘
          │         │
          ▼         ▼
   ┌─────────┐  ┌──────────────┐
   │  Ollama │  │  Anthropic   │
   │  :11434 │  │  Claude API  │
   └─────────┘  └──────────────┘
```

**Routing logic:**
- Token count < 800 AND no complexity keywords → **local Ollama model**
- Token count ≥ 800 OR complexity keyword matched → **cloud Claude model**
- Force local: prefix model name with `ollama/`
- Force cloud: prefix model name with `cloud/`

---

## Agents

| Agent | Purpose | Local Model | Cloud Model | Escalates When |
|-------|---------|-------------|-------------|----------------|
| `app-developer` | Full-stack coding, TDD, clean architecture | qwen2.5-coder:14b | claude-sonnet-4-6 | System design, migrations, perf bottlenecks |
| `testing` | Test generation, coverage, test doubles | qwen2.5-coder:7b | claude-sonnet-4-6 | E2E strategy, load tests, chaos engineering |
| `security` | OWASP Top 10, threat modeling, CVE analysis | qwen2.5-coder:14b | claude-opus-4-8 | Pen test plans, compliance, crypto architecture |
| `devops` | Docker, CI/CD, K8s, monitoring, Terraform | qwen2.5-coder:7b | claude-sonnet-4-6 | Multi-region, disaster recovery, service mesh |
| `code-review` | Correctness, design, perf, security, maintainability | deepseek-r1:14b | claude-sonnet-4-6 | Full codebase audits, architectural reviews |
| `docs` | READMEs, API docs, ADRs, runbooks, changelogs | qwen2.5-coder:7b | claude-sonnet-4-6 | Full onboarding guides, architecture docs |

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker + Compose v2 | 24+ | https://docs.docker.com/get-docker/ |
| Ollama | 0.3+ | https://ollama.com/download |
| VRAM (GPU) | 8 GB min, 16 GB recommended | — |
| RAM | 16 GB min | — |

**Without a GPU:** All models work on CPU but are 5-20x slower. Remove the `deploy.resources` block from `docker-compose.yml` for CPU-only operation.

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <this-repo> personal-agent-stack
cd personal-agent-stack

# 2. Run setup (creates .env, pulls models, starts stack)
./scripts/setup.sh

# 3. First run: edit the generated .env file with your API key
nano infrastructure/.env
# Set ANTHROPIC_API_KEY=sk-ant-...
# Then re-run setup
./scripts/setup.sh
```

That's it. Access:
- **Open WebUI**: http://localhost:3000
- **Router API**: http://localhost:8000
- **Router docs**: http://localhost:8000/docs

---

## Detailed Setup

### Step 1 — Install Ollama

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows: download from https://ollama.com/download
# Verify:
ollama --version
```

### Step 2 — Configure environment

```bash
cp infrastructure/.env.example infrastructure/.env
```

Edit `infrastructure/.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes (for cloud routing) | Get at console.anthropic.com |
| `WEBUI_SECRET_KEY` | Yes | Random string for session signing |
| `LOCAL_MODEL_PRIMARY` | No | Default: `qwen2.5-coder:14b` |
| `LOCAL_MODEL_FAST` | No | Default: `qwen2.5-coder:7b` |
| `LOCAL_MODEL_REASONING` | No | Default: `deepseek-r1:14b` |
| `COMPLEXITY_TOKEN_THRESHOLD` | No | Default: `800`. Raise to keep more work local |

### Step 3 — Pull models

Model sizes and estimated download times on 100 Mbps:

| Model | Size | VRAM needed | Download time |
|-------|------|-------------|---------------|
| qwen2.5-coder:7b | ~4.7 GB | ~5 GB | ~6 min |
| qwen2.5-coder:14b | ~9.0 GB | ~10 GB | ~12 min |
| deepseek-r1:14b | ~9.0 GB | ~10 GB | ~12 min |

```bash
./scripts/pull-models.sh
```

If you have less than 10 GB VRAM, swap `qwen2.5-coder:14b` for `qwen2.5-coder:7b` in `.env`.

### Step 4 — Start the stack

```bash
cd infrastructure
docker compose up -d

# Check all services are healthy
docker compose ps
```

### Step 5 — Create agent models in Ollama

```bash
./scripts/create-agents.sh

# Verify
ollama list | grep agent-
```

---

## VS Code Integration (Continue Extension)

1. Install the **Continue** extension from the VS Code marketplace.

2. Copy the config:
   ```bash
   cp config/vscode/continue.config.json ~/.continue/config.json
   ```

3. Set your Anthropic API key in the environment or directly in the config:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

4. Open VS Code and click the Continue sidebar icon. You'll see all 6 agents plus direct Ollama and Claude access.

**Usage:**
- Select code → `Cmd+Shift+L` → choose agent → ask question
- `Cmd+I` for inline edits (uses App Developer agent by default)
- Tab autocomplete uses `qwen2.5-coder:7b` locally (always fast, no cloud)
- Switch agents from the model dropdown per conversation

---

## Open WebUI Integration

1. Open http://localhost:3000 and create an admin account.

2. The router is already connected as an OpenAI provider (`http://router:8000/v1`). All 6 agents appear as models automatically.

3. Create Workspaces for each agent:
   - Go to **Workspace** → **Models** → select e.g. `app-developer`
   - Set as default for a dedicated chat

4. The router also exposes Ollama models directly. Both appear in the model picker.

---

## Model Routing Logic

The router classifies each request before sending it:

```
1. Is the model name prefixed with "ollama/"?  → force local
2. Is the model name prefixed with "cloud/"?   → force cloud
3. Does the last user message contain any of
   the agent's complexity_keywords?            → cloud
4. Is len(last_message) // 4 > threshold?      → cloud
5. Otherwise                                   → local
```

### Tuning the threshold

- Raise `COMPLEXITY_TOKEN_THRESHOLD` (default 800) to keep more work local.
- Lower it to bias toward cloud for better quality.
- Set it to `99999` to always route local (useful when API key not set).

### Adding keywords

Edit `router/agents.yaml` → add strings to an agent's `complexity_keywords` list → restart the router:
```bash
docker compose -f infrastructure/docker-compose.yml restart router
```

---

## Adding a Custom Agent

1. Add a new entry to `router/agents.yaml`:
   ```yaml
   - id: my-agent
     name: My Agent
     description: Does X
     local_model: qwen2.5-coder:7b
     cloud_model: claude-sonnet-4-6
     complexity_keywords:
       - "complex thing"
     system_prompt: |
       You are...
   ```

2. Create a Modelfile at `config/ollama/Modelfile.my-agent` (copy an existing one as template).

3. Restart the router and create the Ollama model:
   ```bash
   docker compose -f infrastructure/docker-compose.yml restart router
   ollama create agent-my-agent -f config/ollama/Modelfile.my-agent
   ```

The new agent appears immediately in Open WebUI and the Continue model picker.

---

## Troubleshooting

**GPU not detected by Docker**
```bash
# Verify NVIDIA Container Toolkit is installed
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
# If that fails: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
```

**Model runs out of memory (OOM)**
```bash
# Use smaller models
# In infrastructure/.env:
LOCAL_MODEL_PRIMARY=qwen2.5-coder:7b
LOCAL_MODEL_REASONING=deepseek-r1:8b
# Restart router
docker compose -f infrastructure/docker-compose.yml restart router
```

**Router returns 500 for cloud requests**
- Verify `ANTHROPIC_API_KEY` is set in `infrastructure/.env`
- Check router logs: `docker compose -f infrastructure/docker-compose.yml logs router`

**Port conflict (3000 or 8000 already in use)**
```bash
# Edit infrastructure/docker-compose.yml and change the host port:
# "3001:8080" instead of "3000:8080"
```

**Open WebUI can't reach the router**
```bash
# The router URL inside Docker is http://router:8000 (service name, not localhost)
# This is pre-configured. If you changed the service name, update OPENAI_API_BASE_URL.
docker compose -f infrastructure/docker-compose.yml logs open-webui
```

---

## Cost Management

- Tab autocomplete is **always local** — zero cloud cost.
- Simple chats in Open WebUI/Continue route local by default.
- Monitor cloud usage at https://console.anthropic.com/usage
- Set `COMPLEXITY_TOKEN_THRESHOLD=99999` in `.env` to fully disable cloud routing.
- The security agent uses Claude Opus for complexity matches — the most expensive model. Increase its token threshold if cost is a concern.

---

## Directory Structure

```
personal-agent-stack/
├── infrastructure/
│   ├── docker-compose.yml      # Full stack: Ollama, Open WebUI, Router
│   └── .env.example            # Environment template
├── router/
│   ├── main.py                 # FastAPI OpenAI-compatible proxy
│   ├── agents.yaml             # Agent definitions + system prompts
│   ├── requirements.txt
│   └── Dockerfile
├── config/
│   ├── ollama/
│   │   ├── Modelfile.app-dev   # Ollama custom model per agent
│   │   ├── Modelfile.testing
│   │   ├── Modelfile.security
│   │   ├── Modelfile.devops
│   │   ├── Modelfile.code-review
│   │   └── Modelfile.docs
│   └── vscode/
│       └── continue.config.json  # Continue extension config
├── scripts/
│   ├── setup.sh                # One-shot setup script
│   ├── pull-models.sh          # Pull Ollama models
│   └── create-agents.sh        # Create Ollama agent models
└── docs/
    └── DESIGN.md               # Deep-Architect VS Code extension design
```
