$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
& '.\.venv\Scripts\python.exe' -m desktop.main --install-startup
if ($LASTEXITCODE -ne 0) { throw 'Startup registration failed.' }
