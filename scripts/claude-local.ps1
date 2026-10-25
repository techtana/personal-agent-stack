# Launch Claude Code against the local gateway (profile B). Uses a separate config dir so the
# subscription profile (plain `claude`) is untouched. Any extra args go to claude.
#   .\scripts\claude-local.ps1
#   .\scripts\claude-local.ps1 --agent docs
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    $envLines = uv run scripts/stack.py claude-env --shell powershell
    if ($LASTEXITCODE -ne 0) { throw "stack.py claude-env failed" }
    Invoke-Expression ($envLines -join "`n")
    claude @args
} finally { Pop-Location }
