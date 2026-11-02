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
uv sync --quiet
if errorlevel 1 (
    echo Preparing the Python environment failed; see the messages above.
    pause
    exit /b 1
)
rem pythonw opens the window without keeping this console open.
start "" ".venv\Scripts\pythonw.exe" "scripts\installer.py"
