@echo off
rem Restart Jarvis core on Laptop B after an update, so it runs the new code.
rem Asks the core to restart itself (ops\run-core.pyw starts it again in a few seconds). If the core is too old to
rem know how, it stops every pythonw.exe (Jarvis core and, if open, the hub) and starts the core again.
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe"
curl.exe -s -f -X POST -H "X-Jarvis-Session: %JARVIS_CORE_SESSION%" http://127.0.0.1:8770/api/restart >nul 2>&1
if errorlevel 1 (
  echo Restarting the old way...
  taskkill /F /IM pythonw.exe >nul 2>&1
  timeout /t 2 /nobreak >nul
  call "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Jarvis core.cmd"
)
echo Restarting Jarvis core...
timeout /t 6 /nobreak >nul
"%PY%" -m jarvis.core --check --wait 90
echo.
echo If you closed the hub, open it again from the Start menu.
pause
