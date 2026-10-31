$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw 'Install Ollama for Windows from https://ollama.com/download/windows, start it, and rerun this script.'
}
& ollama list
if ($LASTEXITCODE -ne 0) { throw 'Start the Ollama Windows application, then rerun this script.' }
& ollama pull qwen3:0.6b
if ($LASTEXITCODE -ne 0) { throw 'Model download failed.' }
& ollama pull all-minilm
if ($LASTEXITCODE -ne 0) { throw 'Embedding model download failed.' }
Write-Host 'Local model ready. Select qwen3:0.6b and Offline mode in JARVIS settings.'
