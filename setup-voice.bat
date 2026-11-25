@echo off
rem Voice for Jarvis core on Laptop B (run once after setup-core.bat; run again to repair).
rem Installs the voice packages into the core's own Python and downloads the speech-to-text model
rem (Nemotron streaming, ~460 MB) to <Jarvis folder>\models\stt. Then checks everything by saying one line.
cd /d "%~dp0"
set "VENV=%LOCALAPPDATA%\JarvisCore\venv"
if "%JARVIS_ROOT%"=="" set "JARVIS_ROOT=C:\Jarvis"
if not exist "%VENV%\Scripts\python.exe" (echo Run setup-core.bat first. & goto :fail)
echo Installing the voice packages. This takes a few minutes...
"%VENV%\Scripts\python.exe" -m pip install "pipecat-ai[silero]==1.16.0" "sherpa-onnx==2.0.1" "onnxruntime==1.32.0" "anthropic==2.10.0" "websockets==17.4" numpy sounddevice "pywebrtc-audio==0.2.0" || goto :fail
set "MODEL=sherpa-onnx-nemotron-speech-streaming-en-0.6b-560ms-int8-2026-04-25"
set "STT=%JARVIS_ROOT%\models\stt"
if not exist "%STT%\%MODEL%\encoder.int8.onnx" (
  if not exist "%STT%" mkdir "%STT%" || goto :fail
  echo Downloading the speech model, about 460 MB...
  curl.exe -L --fail -o "%STT%\%MODEL%.tar.bz2" "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/%MODEL%.tar.bz2" || goto :fail
  echo Unpacking...
  tar -xjf "%STT%\%MODEL%.tar.bz2" -C "%STT%" || goto :fail
  del "%STT%\%MODEL%.tar.bz2"
)
echo Setting up "hey Jarvis" and the talk key...
"%VENV%\Scripts\python.exe" -m pip install "onnxruntime==1.32.0" "pynput==1.8.2" || goto :fail
"%VENV%\Scripts\python.exe" -m jarvis.voice.wake --download || goto :fail
echo.
if "%JARVIS_SKIP_TALK_CHECK%"=="1" goto :ready
echo Checking: Jarvis should say one line out loud...
"%VENV%\Scripts\python.exe" -m jarvis.voice.talk --check || goto :fail
:ready
echo.
echo Voice is ready. Run restart-core.bat, then open Jarvis Hub and talk: the hub runs the voice by itself.
if not "%JARVIS_NO_PAUSE%"=="1" pause
exit /b 0
:fail
echo.
echo Voice setup did not finish. The messages above say why.
pause
exit /b 1
