@echo off
rem One-time setup for running Jarvis Hub from its code (no installer, so Smart App Control has nothing unsigned to block).
rem Makes a private Python environment in %LOCALAPPDATA%\JarvisHub (outside OneDrive), installs what the hub needs
rem and points the "Jarvis Hub" shortcuts (Start menu and desktop) at this copy. Run it again any time to repair or update the environment.
cd /d "%~dp0"
set "VENV=%LOCALAPPDATA%\JarvisHub\venv"
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
echo Setting up Jarvis Hub. This takes a minute or two...
if not exist "%VENV%\Scripts\python.exe" (%PY% -m venv "%VENV%" || goto :fail)
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul
"%VENV%\Scripts\python.exe" -m pip install -e ".[desktop,client]" || goto :fail
set "HERE=%~dp0"
powershell -NoProfile -Command "$w=New-Object -ComObject WScript.Shell; foreach($d in @([Environment]::GetFolderPath('Programs'),[Environment]::GetFolderPath('Desktop'))){ $s=$w.CreateShortcut($d+'\Jarvis Hub.lnk'); $s.TargetPath=$env:VENV+'\Scripts\pythonw.exe'; $s.Arguments='\"'+$env:HERE+'app.py\"'; $s.WorkingDirectory=$env:HERE; $s.IconLocation=$env:HERE+'ui\icons\app.ico'; $s.Save() }"
echo.
echo Done. Start "Jarvis Hub" from the desktop or the Start menu.
pause
exit /b 0
:fail
echo.
echo Setup did not finish. The messages above say why.
pause
exit /b 1
