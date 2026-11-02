@echo off
rem Agent Stack installer for Windows: double-click this file.
rem Installs uv if missing, prepares the project environment, then opens the installer window, which asks where the
rem models and Python tools go and runs the rest of setup in the background.
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
    echo Installing uv ^(astral.sh^)...
    winget install --id astral-sh.uv --exact --silent --accept-package-agreements --accept-source-agreements
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
where uv >nul 2>nul
if errorlevel 1 (
    echo uv is still not on PATH. Open a new terminal and run install.cmd again.
    pause
    exit /b 1
)
rem Smart App Control only runs signed programs: rebuild .venv on a signed python.org Python if it was made from uv's own.
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\signed-venv.ps1"
if errorlevel 1 (
    pause
    exit /b 1
)
uv sync --quiet
if errorlevel 1 (
    echo Preparing the Python environment failed; see the messages above.
    pause
    exit /b 1
)
rem python.exe, not pythonw.exe: where no signed Python exists, Smart App Control blocks the venv's pythonw.exe
rem launcher (CodeIntegrity 3033) but allows python.exe. The installer hides its own console window as soon as it starts.
set "AGENT_STACK_HIDE_CONSOLE=1"
start "" /min ".venv\Scripts\python.exe" "scripts\installer.py"
