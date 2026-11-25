@echo off
rem Run Jarvis on this laptop by itself (v0.19.0): its own core, voice and tools. No other laptop is needed.
rem Safe to run again: the second time it only checks and switches this laptop's hub back to its own Jarvis.
cd /d "%~dp0"
title Run Jarvis on this laptop
set "VENV=%LOCALAPPDATA%\JarvisCore\venv"
set "JARVIS_NO_PAUSE=1"
set "JARVIS_SKIP_TALK_CHECK=1"
echo This sets Jarvis up to run on this laptop alone.
echo The first time takes 5 to 15 minutes (it downloads the speech model, about 460 MB).
echo.
set "PY="
for %%V in (3.13 3.12) do if not defined PY (py -%%V -c "" >nul 2>nul && set "PY=py -%%V")
if not defined PY (
  echo Getting Python 3.13 for Jarvis ^(your other Python stays as it is^)...
  py install 3.13
  py -3.13 -c "" >nul 2>nul && set "PY=py -3.13"
)
if not defined PY (
  echo Could not find or install Python 3.13.
  goto :fail
)
if not exist "%VENV%\Scripts\python.exe" (%PY% -m venv "%VENV%" || goto :fail)
rem remember the other laptop's Jarvis, so "Use the other laptop's Jarvis.bat" can go back to it
set "REMOTE=0"
if defined JARVIS_CORE_URL (echo %JARVIS_CORE_URL% | findstr /i "127.0.0.1 localhost" >nul || set "REMOTE=1")
if "%REMOTE%"=="1" setx JARVIS_REMOTE_CORE_URL "%JARVIS_CORE_URL%" >nul
if "%REMOTE%"=="1" setx JARVIS_REMOTE_CORE_SESSION "%JARVIS_CORE_SESSION%" >nul
set "JARVIS_CORE_SESSION="
set "JARVIS_CORE_URL="
call setup-core.bat || goto :fail
for /f "tokens=2,*" %%A in ('reg query HKCU\Environment /v JARVIS_CORE_SESSION 2^>nul ^| findstr /i JARVIS_CORE_SESSION') do set "JARVIS_CORE_SESSION=%%B"
set "JARVIS_CORE_URL=http://127.0.0.1:8770"
call setup-voice.bat || goto :fail
call setup-tools.bat || goto :fail
echo.
echo ============================================================
echo Jarvis now runs on this laptop by itself.
echo.
echo 1. Close Jarvis Hub if it is open, then open it again.
echo 2. In the hub: Controls, then Keys. Paste your keys there
echo    (Anthropic, ElevenLabs, Composio). They stay on this laptop.
echo 3. Say "hey Jarvis".
echo.
echo This laptop's Jarvis has its own memory and settings.
echo To go back to the other laptop's Jarvis: "Use the other laptop's Jarvis.bat".
echo ============================================================
pause
exit /b 0
:fail
echo.
echo It did not finish. The messages above say why. Nothing was removed.
pause
exit /b 1
