#!/usr/bin/env bash
# Bootstrap on Linux/macOS/WSL/Git Bash: installs uv if missing, then opens the installer (a window when a display is
# available, otherwise the same questions in the terminal). setup's own flags (--no-pull, --no-restart, --refresh) run
# the unattended `stack.py setup` instead.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv (astral.sh)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
cd "$repo"
for arg in "$@"; do
  case "$arg" in --no-pull|--no-restart|--refresh) exec uv run scripts/stack.py setup "$@" ;; esac
done
exec uv run scripts/stack.py install "$@"
