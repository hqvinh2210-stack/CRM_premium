# Vòng lặp delivery: Code → Review → Test → Deploy → Monitor → Agents

```text
┌─────────┐   ┌─────────┐   ┌──────┐   ┌────────┐   ┌─────────┐
│  CODE   │ → │ REVIEW  │ → │ TEST │ → │ DEPLOY │ → │ MONITOR │
│ Ava/Rex │   │  Kai    │   │pytest│   │ local  │   │ /health │
└────┬────┘   └────┬────┘   └──┬───┘   └───┬────┘   └────┬────┘
     │             │           │           │             │
     └─────────────┴───────────┴───────────┴─────────────┘
                              │ FAIL
                              ▼
                    Linear Issue [AUTO/STAGE]
                              │
                              ▼
              Webhook → orchestrator → LangGraph
                     Ava → Rex → Kai
                              │
                              ▼
                    re-run: python -m pipeline run
```

## Chạy local

```powershell
cd C:\Users\admin\Downloads\CRM\ai-software-company

# Full từ review (khuyến nghị hằng ngày)
uv run python -m pipeline run --from review

# Có agent code trước
uv run python -m pipeline run --from code --task "Fix stock race on concurrent pay"

# Chỉ test
uv run python -m pipeline run --from test --stop-after test --skip-monitor

# Theo dõi production mỗi 60s → lỗi thì tạo Linear task
uv run python -m pipeline monitor --url http://127.0.0.1:8001/health --interval 60

# Báo lỗi tay
uv run python -m pipeline report-error --stage production --summary "Pay 500 on /orders/x/pay" --detail "..."
```

## Biến môi trường

| Var | Ý nghĩa |
|-----|---------|
| `LINEAR_API_KEY` | Tạo issue auto |
| `LINEAR_TEAM_ID` | Team Jiminha |
| `LINEAR_ON_PROD_ERROR=1` | Middleware 500 → Linear |
| `PROD_HEALTH_URL` | URL monitor (default localhost:8001/health) |

## CI (GitHub Actions)

`.github/workflows/ci.yml` trên monorepo CRM:

1. `pipeline run --from review --stop-after review`
2. `pytest`
3. deploy smoke import

## Production errors

`ProductionErrorMiddleware` bắt exception chưa handle → tạo Linear:

```text
[AUTO/PRODUCTION] ValueError on POST /api/v1/orders/.../pay
```

Issue create → webhook (nếu ngrok + orchestrator chạy) → agents xử lý tiếp.

## Report files

Mỗi lần `pipeline run` ghi:

```text
.data/pipeline_runs/run_YYYYMMDDTHHMMSSZ.json
```
