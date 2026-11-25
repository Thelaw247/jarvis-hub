# Builds dist\JarvisHub\JarvisHub.exe (a folder you can keep anywhere, with no Python needed).
# Run from this folder in PowerShell:   .\build.ps1
# Needs Python 3.12 with the app's packages:  python -m pip install . pywebview pyinstaller
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
& $py -m pip install --upgrade pyinstaller
& $py -m PyInstaller --noconfirm --clean --windowed --name JarvisHub --icon ui\icons\app.ico `
    --add-data "ui;ui" `
    --add-data "contracts;contracts" `
    --add-data "VERSION;." `
    --add-data "jarvis_hub/demo/places.json;jarvis_hub/demo" `
    --collect-submodules uvicorn `
    --collect-submodules jarvis_hub `
    --collect-all pymupdf `
    --hidden-import PIL.Image --hidden-import PIL.WebPImagePlugin `
    app.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ""
Write-Host "Built: dist\JarvisHub\JarvisHub.exe"
