@echo off
rem Switch the brain Jarvis talks with: quick (Haiku 5.5) or deep (Sonnet 5.5). Free, no restart needed:
rem it changes from your next sentence. Run "Check tool choices.bat" first to see how the two compare.
cd /d "%~dp0"
"%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe" tools\eval_routing.py --choose
pause
