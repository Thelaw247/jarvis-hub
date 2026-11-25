@echo off
rem Say "hey Jarvis" and watch the score; it fires at 0.50 (set JARVIS_WAKE_THRESHOLD to change it). Ctrl+C to stop.
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%LOCALAPPDATA%\JarvisHub\venv\Scripts\python.exe"
"%PY%" -m jarvis.voice.wake --test
pause
