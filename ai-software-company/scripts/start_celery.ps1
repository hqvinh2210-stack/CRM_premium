# Start Celery worker + beat (requires Redis)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $env:REDIS_URL) { $env:REDIS_URL = "redis://127.0.0.1:6379/0" }
$env:CELERY_ENABLED = "1"

Write-Host "Redis: $env:REDIS_URL"
Write-Host "Starting celery worker -B (beat)..."
uv run celery -A workers.celery_app.celery_app worker -l info -B
