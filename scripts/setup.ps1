param([string]$PythonPath = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot

function Invoke-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Executable $Arguments" }
}

if (-not $PythonPath) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.14-64\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
        'python'
    )
    foreach ($candidate in $candidates) {
        try {
            & $candidate -c 'import sys; assert sys.version_info >= (3,13)' 2>$null
            if ($LASTEXITCODE -eq 0) { $PythonPath = $candidate; break }
        } catch { continue }
    }
}
if (-not $PythonPath) { throw 'Python 3.13+ is required. Install it from python.org, then pass -PythonPath with its full executable path.' }
Invoke-Checked $PythonPath @('-c', 'import sys; assert sys.version_info >= (3,13)')
New-Item -ItemType Directory -Force '.cache\tmp' | Out-Null
$env:TEMP = Join-Path $projectRoot '.cache\tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $projectRoot '.cache\pip'
$env:npm_config_cache = Join-Path $projectRoot '.cache\npm'
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Invoke-Checked $PythonPath @('-m', 'venv', '.venv')
}
Invoke-Checked '.\.venv\Scripts\python.exe' @('-m', 'ensurepip', '--upgrade')
Invoke-Checked '.\.venv\Scripts\python.exe' @('-m', 'pip', 'install', '-r', 'requirements.txt')
if (-not (Test-Path '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
Push-Location frontend
try {
    if (Test-Path 'package-lock.json') { Invoke-Checked 'npm' @('ci', '--no-audit', '--no-fund') }
    else { Invoke-Checked 'npm' @('install', '--no-audit', '--no-fund') }
} finally { Pop-Location }
Write-Host 'Setup complete. Run scripts\test.ps1, then scripts\start-backend.ps1 and scripts\start-frontend.ps1 in separate terminals.'
