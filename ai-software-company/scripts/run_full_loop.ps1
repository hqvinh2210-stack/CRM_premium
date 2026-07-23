# Full stack + delivery loop
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== 1) Ensure API :8001 ==="
$apiUp = $false
try {
  $h = Invoke-RestMethod "http://127.0.0.1:8001/health" -TimeoutSec 2
  $apiUp = $h.ok
} catch { $apiUp = $false }

if (-not $apiUp) {
  Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$Root'; uv run uvicorn app.main:app --host 127.0.0.1 --port 8001"
  Start-Sleep 5
}

Write-Host "=== 2) Ensure UI :5173 ==="
try {
  Invoke-WebRequest "http://127.0.0.1:5173" -UseBasicParsing -TimeoutSec 2 | Out-Null
} catch {
  Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$Root\web'; npm.cmd run dev -- --host 127.0.0.1 --port 5173"
}

Write-Host "=== 3) Pipeline Review → Test → Deploy → Monitor ==="
uv run python -m pipeline run --from review --health-url http://127.0.0.1:8001/health
Write-Host "Exit: $LASTEXITCODE"
Write-Host "POS UI: http://127.0.0.1:5173"
Write-Host "API docs: http://127.0.0.1:8001/docs"
