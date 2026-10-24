param([switch]$SkipFrontend)

$ErrorActionPreference = "Stop"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is required but was not found on PATH."
}

$venv = Join-Path $PSScriptRoot ".venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    python -m venv $venv
}
$python = Join-Path $venv "Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $PSScriptRoot "requirements-dev.txt")

if (-not $SkipFrontend) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm is required for the frontend."
    }
    Push-Location (Join-Path $PSScriptRoot "frontend")
    try { npm ci } finally { Pop-Location }
}

Write-Host "ConceptScape dependencies are installed. Copy .env.example to .env and configure providers before running the pipeline."
