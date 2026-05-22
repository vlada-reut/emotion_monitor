@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo Virtual environment was not found.
    echo Run setup_env.bat first, then start the app again.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "%~dp0main.py"
