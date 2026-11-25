@echo off
rem Jarvis's tools on Laptop B (run once after setup-voice.bat; run again to repair). JARVIS_DESIGN_TOOLS.md.
rem Installs: the Jarvis browser (Playwright, using the Google Chrome or Microsoft Edge already on Windows, nothing to download),
rem PDF/Word/Excel/PowerPoint reading, and Claude agents for tasks and research. Then checks it all and restarts
rem the core so Jarvis has his tools.
cd /d "%~dp0"
set "VENV=%LOCALAPPDATA%\JarvisCore\venv"
if not exist "%VENV%\Scripts\python.exe" (echo Run setup-core.bat first. & goto :fail)
echo Installing Jarvis's tools. This takes a few minutes (the agent package is about 170 MB)...
"%VENV%\Scripts\python.exe" -m pip install "anthropic==2.10.0" "claude-agent-sdk==0.2.183" "playwright==1.63.0" "markitdown[pdf,docx,pptx,xlsx]==0.1.7" "pymupdf>=1.24" "pyyaml>=6" || goto :fail
echo.
echo Checking...
"%VENV%\Scripts\python.exe" -m jarvis.tools.check --browser || goto :fail
echo.
echo Restarting Jarvis core so he has his tools...
curl.exe -s -f -X POST -H "X-Jarvis-Session: %JARVIS_CORE_SESSION%" http://127.0.0.1:8770/api/restart >nul 2>&1
timeout /t 6 /nobreak >nul
echo.
echo Done. Next: double-click "Sign in to a site.bat" and sign in to Canvas in the window that opens.
if not "%JARVIS_NO_PAUSE%"=="1" pause
exit /b 0
:fail
echo.
echo Tools setup did not finish. The messages above say why.
pause
exit /b 1
