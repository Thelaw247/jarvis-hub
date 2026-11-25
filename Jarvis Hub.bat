@echo off
rem Starts Jarvis Hub from its code without leaving a terminal window open. Run setup.bat once first.
cd /d "%~dp0"
set "VENV=%LOCALAPPDATA%\JarvisHub\venv"
if not exist "%VENV%\Scripts\pythonw.exe" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
start "" "%VENV%\Scripts\pythonw.exe" app.py %*
