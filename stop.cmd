@echo off
rem Agent Stack: double-click to close the tray app and stop every service it runs (Ollama keeps running).
rem Same as the tray menu's "Stop services and quit", but works when the tray has already been quit.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo The project environment is missing. Run install.cmd first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "scripts\stack.py" tray --stop
".venv\Scripts\python.exe" "scripts\stack.py" down
if errorlevel 1 (
    pause
    exit /b 1
)
timeout /t 3 >nul
