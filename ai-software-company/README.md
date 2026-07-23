# AI Software Company

Multi-agent software company scaffold (FastAPI + LangGraph).

## Setup

```powershell
cd C:\Users\admin\Downloads\CRM\ai-software-company
.venv\Scripts\activate
uv sync
```

## Delivery loop (Code → Review → Test → Deploy → Monitor)

```powershell
# One-shot full loop (đã chạy SUCCESS)
uv run python -m pipeline run --from review --health-url http://127.0.0.1:8001/health

# Continuous monitor — fail → Linear [AUTO/PRODUCTION] → agents
uv run python -m pipeline monitor --url http://127.0.0.1:8001/health --interval 60

# Start script
powershell -File scripts/start_loop.ps1
```

| Endpoint | Ý nghĩa |
|----------|---------|
| `GET /pipeline/status` | Report run gần nhất |
| `POST /pipeline/run` | Trigger loop qua API |
| `GET /health` | Monitor target |

Fail bất kỳ stage → Linear issue → webhook → Ava/Rex/Kai.  
Chi tiết: `docs/DELIVERY_LOOP.md`

## Full stack (Phase 1–3 core)

| Area | Endpoints |
|------|-----------|
| Loyalty | `GET /api/v1/loyalty/program`, `/points/{id}`, `/rewards` |
| Inventory | `POST /inventory/transfers`, `/stocktake`, `GET /low-stock` |
| Promos | `GET/POST /promotions`, `POST /promotions/orders/{id}/apply` |
| AI | `GET /ai/recommend`, `/ai/coach` |
| Payments | `POST /payments/intent`, `/capture` (sandbox VN) |
| Events | `POST /events/process`, `GET /events/outbox` |
| RFM | `GET /reports/rfm` |

Promo demo: `SALE10` · Login: `cashier@example.com` / `cashier123`

## POS + CRM Phase 1 (MVP) — API

```powershell
uv run uvicorn app.main:app --reload --port 8001
# OpenAPI: http://127.0.0.1:8001/docs
```

**Demo accounts (seeded on startup):**

| User | Password | Role |
|------|----------|------|
| `admin@example.com` | `admin123` | admin |
| `cashier@example.com` | `cashier123` | cashier |

**Checkout flow:**

```powershell
# 1) Login
$login = Invoke-RestMethod http://127.0.0.1:8001/api/v1/auth/login -Method POST -ContentType "application/json" -Body '{"email":"cashier@example.com","password":"cashier123"}'
$token = $login.access_token
$store = $login.store_id
$h = @{ Authorization = "Bearer $token"; "X-Store-Id" = $store }

# 2) Products
Invoke-RestMethod http://127.0.0.1:8001/api/v1/products -Headers $h

# 3) Create order + add line + pay
$order = Invoke-RestMethod http://127.0.0.1:8001/api/v1/orders -Method POST -Headers $h -ContentType "application/json" -Body '{}'
# ... add product_id from list, then POST /orders/{id}/pay with Idempotency-Key
```

| Module | Routes |
|--------|--------|
| Auth | `/api/v1/auth/login`, `/me`, `/stores` |
| Catalog | `/api/v1/products`, `/stock/adjust` |
| Orders | `/api/v1/orders`, `.../pay`, `.../receipt` |
| Customers | `/api/v1/customers/search` |
| Reports | `/api/v1/reports/daily-sales` |

DB default: SQLite `.data/pos.db` (set `DATABASE_URL` for Postgres).

## POS Frontend (React)

```powershell
# Terminal A — API
uv run uvicorn app.main:app --reload --port 8001

# Terminal B — UI
cd web
npm.cmd run dev
```

Mở **http://127.0.0.1:5173**

- Login: `cashier@example.com` / `cashier123`
- Grid sản phẩm + barcode
- Giỏ hàng, giảm %, khách hàng, thanh toán cash
- Hóa đơn popup + màn **Cuối ngày**

## Phase 2 — FastAPI

```powershell
uv run uvicorn app.main:app --reload --port 8001
```

Open http://localhost:8001 → `{"status":"running"}`

> Port **8001** mặc định ở đây để không đụng orchestrator Linear webhook (port 8000).

## Phase 3–4+ — LangGraph pipeline

```text
START → planner → coding → review → END
```

```powershell
# CLI smoke test
uv run python -m graph.graph

# unit test
uv run python -m pytest tests/test_graph.py -q
```

### HTTP

```powershell
uv run uvicorn app.main:app --reload --port 8001
```

```http
POST /run
{"task": "Create Login API"}
```

Returns `plan`, `code`, `review`, `status`, `logs`.

## Linear → LangGraph

```text
Linear Issue Created
        ↓
  ngrok → orchestrator :8000  POST /linear
        ↓
  ai-software-company :8001  POST /run
        ↓
  planner → coding → review
```

**Terminals (cần cả 2 service):**

```powershell
# 1) LangGraph API
cd C:\Users\admin\Downloads\CRM\ai-software-company
uv run uvicorn app.main:app --reload --port 8001

# 2) Linear webhook (ngrok trỏ vào đây)
cd C:\Users\admin\Downloads\CRM\orchestrator
uv run uvicorn main:app --reload --port 8000

# 3) Public URL
ngrok http 8000
```

Linear webhook URL: `https://<ngrok-host>/linear`  
(Events: Issue — create sẽ chạy pipeline; update bị ignore.)

Kiểm tra kết quả gần nhất:

```text
GET http://127.0.0.1:8000/linear/last
GET http://127.0.0.1:8001/linear/last
```

## Agents & roles

| id | Name | Title | Output |
|----|------|-------|--------|
| `planner` | Ava | Product / Tech Planner | `plan` |
| `coder` | Rex | Software Engineer | `code` |
| `reviewer` | Kai | Staff Code Reviewer | `review` |

```text
START → Ava (plan) → Rex (code) → Kai (review) → END
```

```powershell
# list roles
Invoke-RestMethod http://127.0.0.1:8001/agents/roles

# run multi-agent pipeline
Invoke-RestMethod http://127.0.0.1:8001/run -Method POST -ContentType "application/json" -Body '{"task":"Create Login API"}'
```

### Bật LLM (SpaceXAI / xAI)

```powershell
copy .env.example .env
# edit .env → set XAI_API_KEY=...
```

Không có credit API → agents **offline**; memory **local** vẫn chạy.

## Memory (Mem0 + local)

Shared brain để agents / runs hiểu nhau:

```text
START → memory.recall → Ava → Rex → Kai → memory.remember
              ↑_______________________________|
```

| Backend | Khi nào |
|---------|---------|
| **local** (JSONL `.mem0/local_memories.jsonl`) | Luôn bật, không cần credit |
| **Mem0 + Gemini** | `MEM0_USE_REMOTE=1` + `GEMINI_API_KEY` → hybrid |

```env
MEM0_PROVIDER=gemini
MEM0_USE_REMOTE=1
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash-lite
GEMINI_EMBED_MODEL=models/gemini-embedding-001
```

```powershell
# seed memory
Invoke-RestMethod http://127.0.0.1:8001/memory -Method POST -ContentType "application/json" `
  -Body '{"text":"All auth APIs must use JWT","agent_id":"company"}'

# search
Invoke-RestMethod "http://127.0.0.1:8001/memory/search?q=JWT"

# list
Invoke-RestMethod http://127.0.0.1:8001/memory
```

`POST /run` trả thêm `memory_hits`, `memory_context`, `run_id`.

## Structure

```text
ai-software-company/
  app/          # FastAPI + Linear webhook
  graph/        # LangGraph state + nodes
  agents/       # roles + planner/coder/reviewer
  tools/
  config/       # settings (XAI_*)
  tests/
  docs/
```


## Packages (installed)

fastapi, uvicorn, langgraph, langchain, langchain-openai, langchain-community, pydantic, python-dotenv

Chưa cài: Mem0, Redis, PostgreSQL.
