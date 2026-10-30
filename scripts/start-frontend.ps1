$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Join-Path (Split-Path $PSScriptRoot -Parent) 'frontend')
& npm run dev
if ($LASTEXITCODE -ne 0) { throw 'Frontend exited with an error.' }
