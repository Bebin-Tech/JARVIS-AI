$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path 'frontend\dist\index.html')) { throw 'Run npm run build --prefix frontend first.' }
& '.\.venv\Scripts\python.exe' -m backend.desktop
if ($LASTEXITCODE -ne 0) { throw 'Desktop application exited with an error.' }
