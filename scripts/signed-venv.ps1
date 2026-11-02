# Make sure the project environment runs on a signed Python, so Smart App Control lets its pythonw.exe start.
# uv's own Python builds are unsigned; Smart App Control refused .venv\Scripts\pythonw.exe built from one (CodeIntegrity
# 3033, 2026-11-01). A venv made from a python.org Python gets launchers signed by the Python Software Foundation.
# Called by install.cmd and setup.ps1 before `uv sync`; pyproject.toml's python-preference = "system" makes that sync
# pick the signed Python. Does nothing when the existing environment is already signed.
param([string]$Repo = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$venv = Join-Path $Repo '.venv'
$launcher = Join-Path $venv 'Scripts\pythonw.exe'
if ((Test-Path $launcher) -and (Get-AuthenticodeSignature $launcher).Status -eq 'Valid') { exit 0 }

function Find-SignedPython {
    $found = uv python list --only-installed --no-managed-python --output-format json 2>$null | ConvertFrom-Json
    $found | Where-Object {
        $_.version_parts.major -eq 3 -and $_.version_parts.minor -ge 11 -and
        (Get-AuthenticodeSignature $_.path).Status -eq 'Valid'
    } | Sort-Object { $_.version_parts.minor } -Descending | Select-Object -First 1
}

$signed = Find-SignedPython
if (-not $signed) {
    $sac = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy' -ErrorAction SilentlyContinue).VerifiedAndReputablePolicyState
    if ($sac -ne 1) { exit 0 }   # Smart App Control off: uv's own Python is fine
    Write-Host "Smart App Control is on and no signed Python is installed; installing Python 3.13 from python.org (per user)..."
    winget install --id Python.Python.3.13 --exact --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Host
    $signed = Find-SignedPython
    if (-not $signed) { Write-Host "Could not install a signed Python; the installer falls back to python.exe."; exit 0 }
}
if (Test-Path $venv) {
    Write-Host "Rebuilding .venv on $($signed.path) (signed), so Smart App Control allows it..."
    try { Remove-Item -Recurse -Force $venv }
    catch {
        Write-Host "Could not remove .venv ($($_.Exception.Message)). Stop the tray (uv run scripts/stack.py tray --stop) and try again."
        exit 1
    }
}

exit 0
