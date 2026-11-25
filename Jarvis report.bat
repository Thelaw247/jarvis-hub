@echo off
rem One page on what works on this laptop, saved where Claude can read it (OneDrive > Documents > JarvisHub > reports).
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%LOCALAPPDATA%\JarvisHub\venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Jarvis is not set up on this laptop yet.
  pause
  exit /b 1
)
"%PY%" tools\doctor.py
pause
