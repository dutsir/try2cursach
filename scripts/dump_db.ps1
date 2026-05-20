# Full binary dump of price_monitor DB (custom format).
# Compatible with TimescaleDB + pgvector.
#
# Usage:
#   .\scripts\dump_db.ps1
#   .\scripts\dump_db.ps1 -OutputDir D:\backups
#
# Reads DB_NAME / DB_USER / DB_HOST / DB_PORT / DB_PASSWORD from .env
# Requires pg_dump.exe in PATH or C:\Program Files\PostgreSQL\<ver>\bin

param(
    [string]$OutputDir = "backups",
    [string]$EnvFile  = ".env"
)

$ErrorActionPreference = "Stop"

# --- 1. Read .env ---
if (-not (Test-Path $EnvFile)) {
    Write-Error ".env not found: $EnvFile"
    exit 1
}

$envVars = @{}
Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
        $key, $value = $line.Split('=', 2)
        $envVars[$key.Trim()] = $value.Trim()
    }
}

$dbName = $envVars['DB_NAME']
$dbUser = $envVars['DB_USER']
$dbHost = if ($envVars['DB_HOST']) { $envVars['DB_HOST'] } else { 'localhost' }
$dbPort = if ($envVars['DB_PORT']) { $envVars['DB_PORT'] } else { '5432' }
$dbPass = $envVars['DB_PASSWORD']

if (-not $dbName -or -not $dbUser) {
    Write-Error "DB_NAME and DB_USER must be set in .env"
    exit 1
}

# --- 2. Find pg_dump.exe ---
$pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
if (-not $pgDump) {
    $candidates = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\pg_dump.exe' -ErrorAction SilentlyContinue
    if ($candidates) {
        $pgDump = $candidates | Sort-Object FullName -Descending | Select-Object -First 1
    }
}
if (-not $pgDump) {
    Write-Error "pg_dump not found. Install PostgreSQL or add pg_dump.exe to PATH."
    exit 1
}

$pgDumpPath = if ($pgDump -is [System.IO.FileInfo]) { $pgDump.FullName } else { $pgDump.Source }
Write-Host "Using pg_dump: $pgDumpPath" -ForegroundColor Cyan

# --- 3. Prepare output dir ---
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}
$ts = Get-Date -Format "yyyy-MM-dd_HHmm"
$dumpFile = Join-Path $OutputDir "${dbName}_${ts}.dump"

# --- 4. Run pg_dump (-Fc = custom binary, restore via pg_restore) ---
$env:PGPASSWORD = $dbPass

Write-Host "Dumping to: $dumpFile" -ForegroundColor Cyan
& $pgDumpPath `
    -h $dbHost -p $dbPort -U $dbUser `
    -Fc --no-owner --no-acl --no-tablespaces `
    -f $dumpFile `
    $dbName

if ($LASTEXITCODE -ne 0) {
    Write-Error "pg_dump failed with code $LASTEXITCODE"
    exit $LASTEXITCODE
}

$size = (Get-Item $dumpFile).Length
$sizeMb = [math]::Round($size / 1MB, 2)
Write-Host "OK: dump created, size $sizeMb MB" -ForegroundColor Green
Write-Host ""
Write-Host "To restore on Ubuntu/Docker:"
Write-Host "  1. Copy file to new machine"
Write-Host "  2. docker-compose up postgres -d"
Write-Host "  3. bash scripts/restore_db.sh backups/$(Split-Path -Leaf $dumpFile)"
