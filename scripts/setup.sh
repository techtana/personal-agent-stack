#!/usr/bin/env bash
# Bootstrap on Linux/macOS/WSL/Git Bash: installs uv if missing, then hands over to the CLI.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv (astral.sh)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
cd "$repo"
exec uv run scripts/stack.py setup "$@"
