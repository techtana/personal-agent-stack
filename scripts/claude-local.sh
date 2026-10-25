#!/usr/bin/env bash
# Launch Claude Code against the local gateway (profile B); see claude-local.ps1.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo"
eval "$(uv run scripts/stack.py claude-env --shell bash)"
exec claude "$@"
