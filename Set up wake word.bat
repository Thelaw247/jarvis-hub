@echo off
rem "Hey Jarvis" and push-to-talk for the voice window (v0.13.0). Run once; safe to run again.
rem Installs onnxruntime and pynput into the core's Python and downloads the hey_jarvis model (~3 MB in all)
rem to <Jarvis folder>\voice\wakeword. Then you can try it: say "hey Jarvis" and watch the score.
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\JarvisCore\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%LOCALAPPDATA%\JarvisHub\venv\Scripts\python.exe"
if not exist "%PY%" (echo Run setup-core.bat first. & goto :fail)
echo Installing the wake word and the talk key...
"%PY%" -m pip install "onnxruntime==1.32.0" "pynput==1.8.2" || goto :fail
"%PY%" -m jarvis.voice.wake --download || goto :fail
echo.
echo Done. Now say "hey Jarvis" a few times (and some other things) to see it work. Ctrl+C when you're happy.
"%PY%" -m jarvis.voice.wake --test
pause
exit /b 0
:fail
echo.
echo It did not finish. The messages above say why.
pause
exit /b 1
