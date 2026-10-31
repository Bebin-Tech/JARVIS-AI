param([switch]$Paused)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$pythonWindowless = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
$entryPoint = Join-Path $projectRoot 'desktop\main.py'
if (-not (Test-Path $pythonWindowless)) { throw 'Run setup.ps1 and setup-models.ps1 first.' }
if ($Paused) {
    Start-Process -FilePath $pythonWindowless -ArgumentList @(('"' + $entryPoint + '"'), '--paused') -WorkingDirectory $projectRoot -WindowStyle Hidden
} else {
    Start-Process -FilePath $pythonWindowless -ArgumentList @(('"' + $entryPoint + '"'), '--supervise') -WorkingDirectory $projectRoot -WindowStyle Hidden
}
