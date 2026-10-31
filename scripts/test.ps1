$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force '.cache\tmp' | Out-Null
$env:TEMP = Join-Path $PWD '.cache\tmp'
$env:TMP = $env:TEMP
& '.\.venv\Scripts\python.exe' -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
& '.\.venv\Scripts\python.exe' -m ruff check backend desktop scripts/verify-native.py
if ($LASTEXITCODE -ne 0) { throw 'Backend lint failed.' }
Push-Location frontend
try {
    & npm run lint
    if ($LASTEXITCODE -ne 0) { throw 'Frontend lint failed.' }
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
