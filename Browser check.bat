@echo off
rem Browser check: runs Jarvis's own browser code in a throwaway folder and prints each step with timings.
rem A browser window opens on the Canvas sign-in page: no need to sign in, just close it.
cd /d "%~dp0"
"%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe" tools\diag_browser.py > "C:\Jarvis\logs\browser-check.txt" 2>&1
type "C:\Jarvis\logs\browser-check.txt"
echo.
echo Done. Claude can read this from C:\Jarvis\logs\browser-check.txt
pause
