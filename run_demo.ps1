param([switch]$SkipFrontend, [switch]$SkipValidation)

$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
if (-not $SkipValidation) { & $python scripts\validate_artifacts.py }

$api = Start-Process $python -ArgumentList "run_api.py" -WorkingDirectory $PSScriptRoot -PassThru
$frontend = $null
if (-not $SkipFrontend) {
    $frontend = Start-Process npm -ArgumentList "run","dev" -WorkingDirectory (Join-Path $PSScriptRoot "frontend") -PassThru
}

Write-Host "API started with PID $($api.Id) at http://127.0.0.1:8000"
if ($frontend) { Write-Host "Frontend started with PID $($frontend.Id) at http://localhost:3000" }
Write-Host "Close this PowerShell session to stop the demo processes."
