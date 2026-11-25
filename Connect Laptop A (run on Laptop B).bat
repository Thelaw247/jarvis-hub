@echo off
rem Run this on LAPTOP B. It lets Laptop A reach Jarvis core over Tailscale, on your own devices only:
rem   1. shares the core on your tailnet (tailscale serve; never funnel, so it is never on the internet),
rem   2. tells the core its tailnet name and restarts it so it accepts that name,
rem   3. pairs "laptop-a" and leaves its address and token in laptop-a.pairing in OneDrive\Documents\JarvisHub (works
rem      from that folder or from your Jarvis folder). OneDrive carries it
rem      to Laptop A, where "Set up Laptop A.bat" saves it in your settings and deletes the file. The token is never shown.
setlocal
set "HERE=%~dp0"
set "DROP=%OneDrive%\Documents\JarvisHub\"
if not exist "%DROP%" set "DROP=%HERE%"
set "VENV=%LOCALAPPDATA%\JarvisCore\venv"
set "CODE=%USERPROFILE%\Jarvis"
if not exist "%CODE%\jarvis\core\app.py" set "CODE=%HERE:~0,-1%"
if not exist "%VENV%\Scripts\python.exe" (echo This is for Laptop B, where Jarvis core runs. Run setup-core.bat there first. & goto :fail)
set "TS=tailscale"
where tailscale >nul 2>nul || set "TS=%ProgramFiles%\Tailscale\tailscale.exe"
if /i not "%TS%"=="tailscale" if not exist "%TS%" (
  echo Tailscale isn't installed on this laptop. Install it from https://tailscale.com/download, sign in,
  echo do the same on Laptop A with the same account, then run this again.
  goto :fail
)
set "HOST="
for /f "usebackq delims=" %%N in (`powershell -NoProfile -Command "try { $s = & '%TS%' status --json | ConvertFrom-Json; $s.Self.DNSName.TrimEnd('.') } catch { '' }"`) do set "HOST=%%N"
if "%HOST%"=="" (echo Tailscale isn't signed in on this laptop. Open Tailscale, sign in, then run this again. & goto :fail)
echo This laptop on your tailnet: %HOST%
echo Sharing Jarvis core on your tailnet only...
"%TS%" serve --bg --https=443 http://127.0.0.1:8770
if errorlevel 1 (
  echo.
  echo Tailscale didn't share it. If it printed a link above, open it, allow HTTPS for your tailnet, and run this again.
  goto :fail
)
setx JARVIS_CORE_HOSTS "%HOST%" >nul
set "JARVIS_CORE_HOSTS=%HOST%"
echo Restarting Jarvis core so it answers to that name...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*run-core.pyw*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
curl.exe -s -f -X POST -H "X-Jarvis-Session: %JARVIS_CORE_SESSION%" http://127.0.0.1:8770/api/restart >nul 2>&1
timeout /t 4 /nobreak >nul
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if exist "%STARTUP%\Jarvis core.cmd" (
  start "" /D "%CODE%" cmd /c "%STARTUP%\Jarvis core.cmd"
) else (
  if "%JARVIS_ROOT%"=="" set "JARVIS_ROOT=C:\Jarvis"
  start "" /D "%CODE%" "%VENV%\Scripts\pythonw.exe" "%CODE%\ops\run-core.pyw"
)
pushd "%CODE%"
"%VENV%\Scripts\python.exe" -m jarvis.core --check --wait 90 >nul 2>&1 || (popd & echo Jarvis core didn't come back. Run restart-core.bat, then this again. & goto :fail)
set "TOKEN="
for /f "usebackq delims=" %%T in (`"%VENV%\Scripts\python.exe" -m jarvis.core --pair laptop-a`) do set "TOKEN=%%T"
popd
if "%TOKEN%"=="" (echo Pairing Laptop A didn't work. & goto :fail)
(
  echo url=https://%HOST%
  echo session=%TOKEN%
) > "%DROP%laptop-a.pairing"
set "TOKEN="
echo Checking that Jarvis answers over the tailnet...
curl.exe -s -f -m 20 -o nul "https://%HOST%/healthz" && echo   It does. || echo   Not yet over the tailnet (the share can take a minute). Laptop A's setup checks again.
echo.
echo Done. Laptop A is paired. Wait until OneDrive has synced (a few seconds), then run "Set up Laptop A.bat" on Laptop A.
pause
exit /b 0
:fail
echo.
echo It did not finish. The messages above say why.
pause
exit /b 1
