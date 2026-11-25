@echo off
rem Which speech-to-text model is fastest on this laptop? Downloads the 160 ms Nemotron model (about 460 MB, once)
rem next to the one Jarvis uses, then times both on test recordings. Results go to C:\Jarvis\logs\stt-bench.txt.
cd /d "%~dp0"
set "VENV=%LOCALAPPDATA%\JarvisCore\venv"
if "%JARVIS_ROOT%"=="" set "JARVIS_ROOT=C:\Jarvis"
set "STT=%JARVIS_ROOT%\models\stt"
set "M160=sherpa-onnx-nemotron-speech-streaming-en-0.6b-160ms-int8-2026-04-25"
if not exist "%STT%\%M160%\encoder.int8.onnx" (
  echo Downloading the 160 ms model, about 460 MB...
  curl.exe -L --fail -o "%STT%\%M160%.tar.bz2" "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/%M160%.tar.bz2" || goto :fail
  tar -xjf "%STT%\%M160%.tar.bz2" -C "%STT%" || goto :fail
  del "%STT%\%M160%.tar.bz2"
)
"%VENV%\Scripts\python.exe" tools\bench_stt.py
pause
exit /b 0
:fail
echo The benchmark did not finish. The messages above say why.
pause
exit /b 1
