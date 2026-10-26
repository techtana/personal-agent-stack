# Bootstrap on Windows: installs uv if missing, then hands over to the cross-platform CLI.
#   .\scripts\setup.ps1                 # doctor + profile + env + build + pull core models
#   .\scripts\setup.ps1 -Args @('--no-pull')
param([string[]]$Args = @())
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv (astral.sh)..."
    winget install --id astral-sh.uv --exact --silent --accept-package-agreements --accept-source-agreements
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}
Push-Location $repo
try { uv run scripts/stack.py setup @Args } finally { Pop-Location }
