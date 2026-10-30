$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
& npm run build --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
$frontendAssets = Join-Path $PWD 'frontend\dist'
& '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm --onedir --name JarvisAI --distpath release --workpath .cache\pyinstaller --specpath .cache --paths . --add-data "$frontendAssets;frontend/dist" --collect-all piper --collect-all faster_whisper --collect-all openwakeword --collect-all onnxruntime --collect-all ctranslate2 --hidden-import webview.platforms.edgechromium --hidden-import keyring.backends.Windows backend\desktop.py
if ($LASTEXITCODE -ne 0) { throw 'Desktop packaging failed.' }
Copy-Item -LiteralPath models -Destination release\JarvisAI\models -Recurse -Force
Write-Host 'Build ready: release\JarvisAI\JarvisAI.exe. Keep its models and _internal directories alongside it.'
