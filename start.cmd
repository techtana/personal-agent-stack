@echo off
rem Agent Stack: double-click to start the tray app and its services after install.cmd has run.
rem If the tray is already running, this opens its window instead. Also (re)creates the Start menu entry "Agent Stack".
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo The project environment is missing. Run install.cmd first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "scripts\stack.py" tray --show
if errorlevel 1 (
    echo.
    echo The tray app did not start; see the messages above and .run\logs\tray.log.
    pause
    exit /b 1
)
