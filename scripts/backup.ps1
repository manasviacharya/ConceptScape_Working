param([string]$OutputDir = "backups")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root $OutputDir
New-Item -ItemType Directory -Force -Path $target | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$databaseUrl = $env:CONCEPTSCAPE_DATABASE_URL
if ($databaseUrl -and $databaseUrl.StartsWith("postgres")) {
  if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) { throw "pg_dump is required for PostgreSQL backups." }
  & pg_dump $databaseUrl --format=custom --file (Join-Path $target "conceptscape-$stamp.dump")
} else {
  $db = Join-Path $root "conceptscape.db"
  if (Test-Path $db) { Copy-Item $db (Join-Path $target "conceptscape-$stamp.db") }
}
$workspaceRoot = Join-Path $root "workspaces"
if (Test-Path $workspaceRoot) { Compress-Archive -Path $workspaceRoot -DestinationPath (Join-Path $target "workspaces-$stamp.zip") }
Write-Host "Backup written to $target"
