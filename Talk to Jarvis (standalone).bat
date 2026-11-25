@echo off
rem Talk to Jarvis without the core (the voice loop runs in this window; prints latency per turn). For testing.
cd /d "%~dp0"
if "%JARVIS_ROOT%"=="" set "JARVIS_ROOT=C:\Jarvis"
"%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe" -m jarvis.voice.talk %*
pause
