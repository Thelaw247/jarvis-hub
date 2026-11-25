@echo off
rem Stops the test recording now (it also stops by itself after 20 minutes).
cd /d "%~dp0"
"%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe" -m jarvis.voice.diagnose off
pause
