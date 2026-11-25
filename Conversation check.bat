@echo off
rem Conversation check: does Jarvis catch each instruction once, ignore noise, and not hear himself?
rem Close the Talk to Jarvis window first. About a minute of prompts. Saves numbers only, never the recording.
cd /d "%~dp0"
"%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe" -m jarvis.voice.turn_check %*
pause
