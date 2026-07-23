# CRM_premium

POS + CRM multi-store (FastAPI) · AI agents (LangGraph) · Linear delivery loop · React SoftPOS.

**Repo:** https://github.com/hqvinh2210-stack/CRM_premium  
**Deploy guide:** [DEPLOY.md](./DEPLOY.md)

## Projects

| Path | Role |
|------|------|
| `ai-software-company/` | POS/CRM API + React UI + Celery workers + Alembic |
| `orchestrator/` | Linear webhook receiver (ngrok → agents) |

## Production (Docker)

```powershell
cd ai-software-company
copy .env.example .env
# edit secrets
docker compose -f docker-compose.prod.yml up -d --build
# UI + API: http://localhost:8001
```

## Dev quick start

```powershell
cd ai-software-company
uv sync
uv run uvicorn app.main:app --reload --port 8001
# other terminal
cd web; npm run dev
```

Login: `admin@example.com` / `admin123` · `cashier@example.com` / `cashier123`

### Linear orchestrator

```powershell
cd orchestrator
uv sync
uv run uvicorn main:app --reload --port 8000
# ngrok http 8000
```
