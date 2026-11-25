@echo off
rem Sign in to a site in the Jarvis browser on Laptop B, so Jarvis can use it as you (Canvas, PAWS, Google...).
rem It opens as a normal Chrome window with no automation attached: you type your password (or let your saved
rem Google passwords fill it in) and do the MFA yourself. Jarvis never sees them. Close the window when you are done.
cd /d "%~dp0"
set "SITE=canvas"
set /p "SITE=Which site? canvas, paws, google, crowdmark, github, or paste a sign-in link [canvas]: "
echo Opening it...
curl.exe -s -S -m 120 -w "\n(status %%{http_code}, %%{time_total} s)\n" -X POST -H "Content-Type: application/json" -H "X-Jarvis-Session: %JARVIS_CORE_SESSION%" -d "{\"site\": \"%SITE%\"}" http://127.0.0.1:8770/api/browser/sign-in > "C:\Jarvis\logs\sign-in-result.txt" 2>&1
type "C:\Jarvis\logs\sign-in-result.txt"
echo.
findstr /c:"status 200" "C:\Jarvis\logs\sign-in-result.txt" >nul
if errorlevel 1 (
  echo That did not work. Tell Claude: it can read the message above.
) else (
  echo The Jarvis browser is open. Sign in there, then close that browser window. Jarvis carries on once it is closed.
)
pause
