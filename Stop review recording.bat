@echo off
rem Stops review recording now. What was recorded stays in C:\Jarvis\logs\review until you delete that folder.
cd /d "%USERPROFILE%\Jarvis"
"%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe" -m jarvis.review off
pause
