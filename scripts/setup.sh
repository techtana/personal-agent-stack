#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="$REPO_ROOT/infrastructure"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }
error() { echo -e "${RED}[error]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
check_dep() {
  if ! command -v "$1" &>/dev/null; then
    error "Required tool not found: $1. $2"
    exit 1
  fi
}

info "Checking dependencies..."
check_dep docker  "Install from https://docs.docker.com/get-docker/"
check_dep ollama  "Install from https://ollama.com/download"
check_dep curl    "Install with your package manager"

# Docker Compose v2
if ! docker compose version &>/dev/null; then
  error "Docker Compose v2 not found. Update Docker Desktop or install the plugin."
  exit 1
fi

# ---------------------------------------------------------------------------
# Environment setup
# ---------------------------------------------------------------------------
if [[ ! -f "$INFRA_DIR/.env" ]]; then
  cp "$INFRA_DIR/.env.example" "$INFRA_DIR/.env"
  warn "Created $INFRA_DIR/.env from template."
  warn "Edit it now and add your ANTHROPIC_API_KEY, then re-run this script."
  warn "  nano $INFRA_DIR/.env"
  exit 0
fi

# Check ANTHROPIC_API_KEY is set (non-empty, non-default)
source "$INFRA_DIR/.env" 2>/dev/null || true
if [[ -z "${ANTHROPIC_API_KEY:-}" ]] || [[ "$ANTHROPIC_API_KEY" == "your-key-here" ]]; then
  warn "ANTHROPIC_API_KEY not configured. Cloud routing will be disabled."
  warn "Set it in $INFRA_DIR/.env to enable Claude API fallback."
fi

# ---------------------------------------------------------------------------
# Start Docker stack
# ---------------------------------------------------------------------------
info "Starting Docker Compose stack..."
cd "$INFRA_DIR"
docker compose up -d --build

# ---------------------------------------------------------------------------
# Wait for Ollama
# ---------------------------------------------------------------------------
info "Waiting for Ollama to be ready..."
TRIES=0
until curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; do
  TRIES=$((TRIES + 1))
  if [[ $TRIES -ge 30 ]]; then
    error "Ollama did not become ready in 60 seconds."
    error "Check logs: docker compose -f $INFRA_DIR/docker-compose.yml logs ollama"
    exit 1
  fi
  sleep 2
done
info "Ollama is ready."

# ---------------------------------------------------------------------------
# Pull models
# ---------------------------------------------------------------------------
info "Pulling local models (this may take a while on first run)..."
"$REPO_ROOT/scripts/pull-models.sh"

# ---------------------------------------------------------------------------
# Create custom agent models
# ---------------------------------------------------------------------------
info "Creating agent Modelfiles in Ollama..."
"$REPO_ROOT/scripts/create-agents.sh"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Agent stack is ready!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  Open WebUI   →  http://localhost:3000"
echo "  Router API   →  http://localhost:8000"
echo "  Router docs  →  http://localhost:8000/docs"
echo "  Ollama API   →  http://localhost:11434"
echo ""
echo "VS Code integration:"
echo "  1. Install the 'Continue' extension"
echo "  2. Copy config/vscode/continue.config.json"
echo "     to ~/.continue/config.json"
echo ""
