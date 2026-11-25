@echo off
rem Which brain should Jarvis talk with? Asks both (quick = Haiku 5.5, deep = Sonnet 5.5) about 50 typical requests
rem and shows, for each: how often it picked the right tool first, and how long until its first word.
rem No tool actually runs, nothing is opened or changed. Costs under 25 cents. Takes a minute or two.
rem At the end it asks which one Jarvis should use. Report: C:\Jarvis\logs\routing-eval.txt
cd /d "%~dp0"
"%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe" tools\eval_routing.py %*
pause
