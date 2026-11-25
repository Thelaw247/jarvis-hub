@echo off
rem Hearing check: how well Jarvis hears you on this mic, and the best mic set-up for your voice.
rem Close the Talk to Jarvis window first. Takes about a minute. Saves numbers only, never the recording.
cd /d "%~dp0"
"%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe" -m jarvis.voice.hearing_check %*
pause
