# Start delivery stack + continuous monitor (Windows)
# Usage: powershell -File scripts/start_loop.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== POS/API :8001 =="
Start-Process -WindowStyle Minimized powershell -ArgumentList @(
  "-NoExit", "-Command",
  "cd '$Root'; uv run uvicorn app.main:app --host 0.0.0.0 --port 8001"
)

Start-Sleep -Seconds 4

Write-Host "== Pipeline once: Review → Test → Deploy → Monitor =="
uv run python -m pipeline run --from review --health-url http://127.0.0.1:8001/health
if ($LASTEXITCODE -ne 0) {
  Write-Host "Pipeline FAILED — check Linear for [AUTO/*] issues"
  exit $LASTEXITCODE
}

Write-Host "== Continuous monitor (60s) — Ctrl+C to stop =="
uv run python -m pipeline monitor --url http://127.0.0.1:8001/health --interval 60
