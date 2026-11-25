@echo off
rem Talk to Jarvis: this laptop's mic and speakers, connected to Jarvis core (the orb and captions show on the hub).
rem Works on Laptop B (core's Python) and Laptop A (the hub's Python, after setup.bat). Add --barge-in with headphones.
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%LOCALAPPDATA%\JarvisHub\venv\Scripts\python.exe"
"%PY%" -m jarvis.voice.client %*
pause
