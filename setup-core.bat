@echo off
rem One-time setup for Jarvis core on Laptop B, run from its code (like setup.bat for the hub).
rem Makes a private Python environment in %LOCALAPPDATA%\JarvisCore (outside OneDrive), installs what the core needs,
rem makes the Jarvis folder (C:\Jarvis, or JARVIS_ROOT) with its runtime folders, and writes a filled-in Servy
rem config for this machine. Run it again any time to repair or update. Details: ops\README.md.
cd /d "%~dp0"
set "VENV=%LOCALAPPDATA%\JarvisCore\venv"
if "%JARVIS_ROOT%"=="" set "JARVIS_ROOT=C:\Jarvis"
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
echo Setting up Jarvis core. This takes a minute or two...
if not exist "%VENV%\Scripts\python.exe" (%PY% -m venv "%VENV%" || goto :fail)
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul
rem The core's dependencies (keep in step with the "core" group in pyproject.toml)
"%VENV%\Scripts\python.exe" -m pip install "fastapi>=0.115" "uvicorn>=0.30" "httpx>=0.27" "keyring>=25" "sqlite-vec>=0.1.9" || goto :fail
for %%D in (memory undo data browser logs) do if not exist "%JARVIS_ROOT%\%%D" mkdir "%JARVIS_ROOT%\%%D" || goto :fail
set "JARVIS_REPO=%~dp0"
if "%JARVIS_REPO:~-1%"=="\" set "JARVIS_REPO=%JARVIS_REPO:~0,-1%"
powershell -NoProfile -Command "$t=Get-Content -Raw 'ops\servy\jarvis-core.json'; $t=$t.Replace('C:\\Jarvis', ($env:JARVIS_ROOT -replace '\\','\\')).Replace('%%LOCALAPPDATA%%', ($env:LOCALAPPDATA -replace '\\','\\')).Replace('%%JARVIS_REPO%%', ($env:JARVIS_REPO -replace '\\','\\')); Set-Content -Encoding UTF8 -Path ($env:LOCALAPPDATA+'\JarvisCore\jarvis-core.servy.json') -Value $t" || goto :fail
"%VENV%\Scripts\python.exe" -c "import jarvis.core.app" || goto :fail
rem Start the core at every sign-in and keep it running (ops\run-core.pyw), unless you use Servy instead.
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if /i not "%JARVIS_USE_SERVY%"=="1" (
  > "%STARTUP%\Jarvis core.cmd" echo @set "JARVIS_ROOT=%JARVIS_ROOT%" ^& start "" "%VENV%\Scripts\pythonw.exe" "%JARVIS_REPO%\ops\run-core.pyw"
  start "" "%VENV%\Scripts\pythonw.exe" "%JARVIS_REPO%\ops\run-core.pyw"
)
echo Waiting for the core to answer...
"%VENV%\Scripts\python.exe" -m jarvis.core --check --wait 90 > "%LOCALAPPDATA%\JarvisCore\setup-result.txt" 2>&1
type "%LOCALAPPDATA%\JarvisCore\setup-result.txt"
rem Pair this laptop's hub with the core once; the token goes straight into your settings and is never shown.
if not defined JARVIS_CORE_SESSION (
  for /f "usebackq delims=" %%T in (`"%VENV%\Scripts\python.exe" -m jarvis.core --pair laptop-b`) do setx JARVIS_CORE_SESSION "%%T" >nul
  setx JARVIS_CORE_URL "http://127.0.0.1:8770" >nul
  echo This laptop's hub is paired with the core.
)
echo.
echo Done. Jarvis folder: %JARVIS_ROOT%
echo The core starts by itself when you sign in. Open http://127.0.0.1:8770/healthz to check it.
echo (Optional, later: Servy instead - set JARVIS_USE_SERVY=1 and see ops\README.md.)
if not "%JARVIS_NO_PAUSE%"=="1" pause
exit /b 0
:fail
echo.
echo Setup did not finish. The messages above say why.
pause
exit /b 1
