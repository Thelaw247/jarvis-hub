@echo off
rem Shows your mic level and whether Jarvis hears you as speech (10 seconds).
cd /d "%~dp0"
if "%JARVIS_ROOT%"=="" set "JARVIS_ROOT=C:\Jarvis"
"%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe" -m jarvis.voice.talk --mic-test
pause
