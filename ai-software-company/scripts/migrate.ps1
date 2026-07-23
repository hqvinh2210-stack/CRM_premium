# Apply Alembic migrations
# Usage: powershell -File scripts/migrate.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $env:DATABASE_URL) {
  Write-Host "DATABASE_URL not set — using default from .env / sqlite"
}
Write-Host "Alembic upgrade head..."
uv run alembic upgrade head
Write-Host "Done. Current:"
uv run alembic current
