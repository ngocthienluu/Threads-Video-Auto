@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Please create .venv and install requirements.txt as described in README.md.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m app.main %*
if errorlevel 1 pause
