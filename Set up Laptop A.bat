@echo off
rem Everything Laptop A needs, in one go (safe to run again):
rem   the hub (its own Python in %LOCALAPPDATA%\JarvisHub, outside OneDrive; Start menu and desktop shortcuts),
rem   the voice window (mic and speakers to Jarvis core, echo cancelling), "hey Jarvis" and the Right Ctrl talk key,
rem   and the connection to Jarvis core on Laptop B, from laptop-a.pairing (made by "Connect Laptop A (run on Laptop B).bat").
setlocal
cd /d "%~dp0"
set "VENV=%LOCALAPPDATA%\JarvisHub\venv"
if "%JARVIS_ROOT%"=="" set "JARVIS_ROOT=C:\Jarvis"
rem Python 3.12 or 3.13: the voice packages (pywebrtc-audio, pyyaml) have no ready-made installs for newer ones yet.
set "PY="
for %%V in (3.13 3.12) do if not defined PY (py -%%V -c "" >nul 2>nul && set "PY=py -%%V")
if not defined PY (
  echo Getting Python 3.13 for Jarvis ^(your other Python stays as it is^)...
  py install 3.13
  py -3.13 -c "" >nul 2>nul && set "PY=py -3.13"
)
if not defined PY goto :nopython
if exist "%VENV%\Scripts\python.exe" "%VENV%\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3,12),(3,13)) else 1)" || (
  echo Rebuilding the hub's Python on 3.13 ^(it was made with a version that's too new^)...
  rmdir /s /q "%VENV%"
)
echo [1/4] The hub. This takes a minute or two...
if not exist "%VENV%\Scripts\python.exe" (%PY% -m venv "%VENV%" || goto :nopython)
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul
"%VENV%\Scripts\python.exe" -m pip install -e ".[desktop,client]" || goto :fail
set "HERE=%~dp0"
powershell -NoProfile -Command "$w=New-Object -ComObject WScript.Shell; foreach($d in @([Environment]::GetFolderPath('Programs'),[Environment]::GetFolderPath('Desktop'))){ $s=$w.CreateShortcut($d+'\Jarvis Hub.lnk'); $s.TargetPath=$env:VENV+'\Scripts\pythonw.exe'; $s.Arguments='\"'+$env:HERE+'app.py\"'; $s.WorkingDirectory=$env:HERE; $s.IconLocation=$env:HERE+'ui\icons\app.ico'; $s.Save(); $old=$d+'\Talk to Jarvis.lnk'; if(Test-Path -LiteralPath $old){ Remove-Item -LiteralPath $old } }"
echo [2/4] "Hey Jarvis" and the talk key...
for %%D in (logs voice) do if not exist "%JARVIS_ROOT%\%%D" mkdir "%JARVIS_ROOT%\%%D"
"%VENV%\Scripts\python.exe" -m pip install "onnxruntime==1.32.0" "pynput==1.8.2" || goto :fail
"%VENV%\Scripts\python.exe" -m jarvis.voice.wake --download || goto :fail
echo [3/4] Connecting to Jarvis core on Laptop B...
set "URL=" & set "SESSION="
if exist "%HERE%laptop-a.pairing" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%HERE%laptop-a.pairing") do (
    if /i "%%A"=="url" set "URL=%%B"
    if /i "%%A"=="session" set "SESSION=%%B"
  )
)
if defined SESSION (
  setx JARVIS_CORE_URL "%URL%" >nul
  setx JARVIS_CORE_SESSION "%SESSION%" >nul
  set "JARVIS_CORE_URL=%URL%"
  del "%HERE%laptop-a.pairing"
  set "SESSION="
  echo   Paired with %URL%
) else if defined JARVIS_CORE_SESSION (
  echo   Already paired with %JARVIS_CORE_URL%
) else (
  echo   Not paired yet. On Laptop B, run "Connect Laptop A (run on Laptop B).bat", then run this again.
  goto :tailscale
)
curl.exe -s -f -m 20 -o nul "%JARVIS_CORE_URL%/healthz" && (echo   Jarvis core answers.) || (echo   Jarvis core doesn't answer yet: check Laptop B is on and Tailscale is connected on both laptops.)
:tailscale
where tailscale >nul 2>nul || if not exist "%ProgramFiles%\Tailscale\tailscale.exe" echo   Tailscale isn't installed here: get it from https://tailscale.com/download and sign in with the same account as Laptop B.
echo [4/4] Your mic: say "hey Jarvis" a few times and watch the score (it fires at 0.50). Ctrl+C when you're done.
"%VENV%\Scripts\python.exe" -m jarvis.voice.wake --test
echo.
echo Done. Open "Jarvis Hub" from the desktop: it listens and talks by itself now ^(the old "Talk to Jarvis" icon is gone^).
echo Say "hey Jarvis", or hold Right Ctrl and talk.
pause
exit /b 0
:nopython
echo Jarvis needs Python 3.13. Get it from https://www.python.org/downloads/release/python-3139/ ^(Windows installer, 64-bit^), install it, then run this again. Your other Python can stay.
:fail
echo.
echo Setup did not finish. The messages above say why.
pause
exit /b 1
