$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
& npm run build --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
$assets = Join-Path $PWD 'frontend\dist'
& '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm --onedir --windowed --name JarvisBackground --distpath release --workpath .cache\pyinstaller-background --specpath .cache --paths . --add-data "$assets;frontend/dist" --collect-all piper --collect-all faster_whisper --collect-all openwakeword --collect-all onnxruntime --collect-all ctranslate2 --hidden-import pystray._win32 --hidden-import win32timezone --hidden-import keyring.backends.Windows desktop\main.py
if ($LASTEXITCODE -ne 0) { throw 'Background build failed.' }
Copy-Item -LiteralPath models -Destination release\JarvisBackground\models -Recurse -Force
Write-Host 'Background build ready: release\JarvisBackground\JarvisBackground.exe'
