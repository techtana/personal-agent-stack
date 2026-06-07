#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELFILE_DIR="$REPO_ROOT/config/ollama"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

declare -A AGENTS=(
  ["agent-app-dev"]="Modelfile.app-dev"
  ["agent-testing"]="Modelfile.testing"
  ["agent-security"]="Modelfile.security"
  ["agent-devops"]="Modelfile.devops"
  ["agent-code-review"]="Modelfile.code-review"
  ["agent-docs"]="Modelfile.docs"
)

for agent_name in "${!AGENTS[@]}"; do
  modelfile="${MODELFILE_DIR}/${AGENTS[$agent_name]}"
  if [[ ! -f "$modelfile" ]]; then
    echo -e "${RED}[error]${NC} Modelfile not found: $modelfile"
    continue
  fi
  echo -e "${GREEN}[create]${NC} $agent_name from ${AGENTS[$agent_name]}"
  ollama create "$agent_name" -f "$modelfile"
done

echo ""
echo "Agent models:"
ollama list | grep "^agent-"
