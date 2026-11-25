@echo off
rem Teach Jarvis your voice: you say 24 short things you would really ask him (about 4 minutes). It shows what he
rem heard for each, and saves a note of what his hearing gets wrong for you, so he can work out what you meant.
rem Close the Talk to Jarvis window first. The recordings stay on this laptop (C:\Jarvis\voice\lessons).
cd /d "%~dp0"
"%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe" -m jarvis.voice.lessons %*
pause
