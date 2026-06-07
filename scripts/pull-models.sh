#!/usr/bin/env bash
set -euo pipefail

MODELS=(
  "qwen2.5-coder:7b"
  "qwen2.5-coder:14b"
  "deepseek-r1:14b"
)

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

already_pulled() {
  ollama list 2>/dev/null | grep -q "^$1 " || ollama list 2>/dev/null | grep -q "^${1%:*}:${1##*:} "
}

for model in "${MODELS[@]}"; do
  if already_pulled "$model"; then
    echo -e "${YELLOW}[skip]${NC} $model already present"
  else
    echo -e "${GREEN}[pull]${NC} Pulling $model..."
    ollama pull "$model"
    echo -e "${GREEN}[done]${NC} $model"
  fi
done

echo ""
echo "Available models:"
ollama list
