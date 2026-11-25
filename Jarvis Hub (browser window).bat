@echo off
rem Same as "Jarvis Hub.bat" but opens the hub in an Edge app window instead of its own window.
cd /d "%~dp0"
set "VENV=%LOCALAPPDATA%\JarvisHub\venv"
start "" "%VENV%\Scripts\pythonw.exe" app.py --browser %*
