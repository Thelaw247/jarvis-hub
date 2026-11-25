@echo off
rem Starts Jarvis Hub with the made-up demo day (no jarvis-core needed), for trying things out. Run setup.bat once first.
cd /d "%~dp0"
set "VENV=%LOCALAPPDATA%\JarvisHub\venv"
if not exist "%VENV%\Scripts\pythonw.exe" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
start "" "%VENV%\Scripts\pythonw.exe" app.py --demo %*
