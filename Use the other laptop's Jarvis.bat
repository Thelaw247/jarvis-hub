@echo off
rem Point this laptop's hub back at the other laptop's Jarvis (what "Run Jarvis on this laptop.bat" remembered).
if not defined JARVIS_REMOTE_CORE_URL (
  echo This laptop has never been connected to another laptop's Jarvis, so there is nothing to go back to.
  pause
  exit /b 1
)
setx JARVIS_CORE_URL "%JARVIS_REMOTE_CORE_URL%" >nul
setx JARVIS_CORE_SESSION "%JARVIS_REMOTE_CORE_SESSION%" >nul
echo Done. Close Jarvis Hub and open it again: it now shows the other laptop's Jarvis.
echo To run Jarvis on this laptop alone again: "Run Jarvis on this laptop.bat".
pause
exit /b 0
