$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force '.cache\tmp' | Out-Null
$env:TEMP = Join-Path $PWD '.cache\tmp'
$env:TMP = $env:TEMP
$env:HF_HOME = Join-Path $PWD '.cache\huggingface'
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw 'Desktop dependency installation failed.' }
& '.\.venv\Scripts\python.exe' -m backend.setup_models
if ($LASTEXITCODE -ne 0) { throw 'Model provisioning failed.' }
