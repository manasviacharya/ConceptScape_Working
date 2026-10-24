param([Parameter(Mandatory=$true)][string]$BackupFile)

$ErrorActionPreference = "Stop"
$databaseUrl = $env:CONCEPTSCAPE_DATABASE_URL
if ($BackupFile.EndsWith(".dump") -and $databaseUrl -and $databaseUrl.StartsWith("postgres")) {
  if (-not (Get-Command pg_restore -ErrorAction SilentlyContinue)) { throw "pg_restore is required." }
  & pg_restore --clean --if-exists --dbname $databaseUrl $BackupFile
} elseif ($BackupFile.EndsWith(".db")) {
  Copy-Item -LiteralPath $BackupFile -Destination (Join-Path (Split-Path -Parent $PSScriptRoot) "conceptscape.db") -Force
} else {
  throw "Unsupported backup format or database configuration."
}
Write-Host "Restore completed."
