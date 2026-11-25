@echo off
rem Record a test conversation, so what Jarvis mishears can be fixed (off by default; you switch it on here).
rem For 20 minutes it keeps, on this laptop only (C:\Jarvis\voice\diagnose): what Jarvis heard, what he said, and your
rem side of each turn as sound. It switches itself off; "Stop recording.bat" stops it sooner.
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe"
if "%~1"=="" ("%PY%" -m jarvis.voice.diagnose on) else ("%PY%" -m jarvis.voice.diagnose %*)
pause
