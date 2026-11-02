# Bootstrap on Windows: installs uv if missing, then hands over to the cross-platform CLI.
#   .\scripts\setup.ps1                 # installer window: choose the models and tools folders, setup runs in the background
#   .\scripts\setup.ps1 -Args @('--no-gui')    # the same questions in this terminal
#   .\scripts\setup.ps1 -Args @('--no-pull')  # unattended `stack.py setup` with the folders already in the profile
# Double-clicking install.cmd in the repository root does the same as the first line.
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
try {
    & (Join-Path $PSScriptRoot 'signed-venv.ps1') -Repo $repo
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    # setup's own flags keep the unattended path that earlier docs and scripts call
    $unattended = @($Args | Where-Object { $_ -in @('setup', '--no-pull', '--no-restart', '--refresh') }).Count -gt 0
    if ($unattended) { uv run scripts/stack.py setup @($Args | Where-Object { $_ -ne 'setup' }) }
    else { uv run scripts/stack.py install @Args }
} finally { Pop-Location }
