# Deploy CRM_premium (production)

Repo: https://github.com/hqvinh2210-stack/CRM_premium

## Architecture

```text
Browser  →  FastAPI :8001  (API /api/v1 + SPA web/dist)
                 │
        ┌────────┼────────┐
        ▼        ▼        ▼
    Postgres   Redis   Celery worker+beat
```

## 1. Push code (GitHub)

```powershell
cd C:\Users\admin\Downloads\CRM
git push -u origin main
```

Remote: `origin` → `https://github.com/hqvinh2210-stack/CRM_premium.git`

**Never commit `.env`** (API keys). Only `.env.example` is tracked.

## 2. Deploy with Docker Compose (VPS / local Docker)

Requirements: Docker Desktop or Docker Engine.

```powershell
cd ai-software-company
copy .env.example .env
# Edit .env: POSTGRES_PASSWORD, XAI_API_KEY, PUBLIC_BASE_URL, payment keys...

docker compose -f docker-compose.prod.yml up -d --build
```

| URL | Mô tả |
|-----|--------|
| http://HOST:8001/ | POS UI (SPA) |
| http://HOST:8001/docs | OpenAPI |
| http://HOST:8001/health | Health |

Demo login: `admin@example.com` / `admin123`

### Stop

```powershell
docker compose -f docker-compose.prod.yml down
```

## 3. Deploy without Docker (VPS Python)

```bash
# Install Postgres + Redis on host, then:
cd ai-software-company
python -m venv .venv && source .venv/bin/activate
pip install uv && uv sync
export DATABASE_URL=postgresql+psycopg://crm:PASS@127.0.0.1:5432/crm_pos
export USE_ALEMBIC=1 REDIS_URL=redis://127.0.0.1:6379/0 CELERY_ENABLED=1 SERVE_WEB=1
cd web && npm ci && npm run build && cd ..
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
# separate terminal:
uv run celery -A workers.celery_app.celery_app worker -l info -B
```

## 4. Free cloud options (connect GitHub repo)

| Platform | Gợi ý |
|----------|--------|
| **Railway** | New Project → Deploy from GitHub → set root `ai-software-company` → add Postgres + Redis plugins → env vars |
| **Render** | Web Service + Postgres + Redis → Docker or native Python |
| **Fly.io** | `fly launch` from `ai-software-company` with Dockerfile |

Env tối thiểu trên cloud:

```env
DATABASE_URL=postgresql+psycopg://...
USE_ALEMBIC=1
REDIS_URL=redis://...
CELERY_ENABLED=1
SERVE_WEB=1
PUBLIC_BASE_URL=https://your-app.example.com
CORS_ORIGINS=https://your-app.example.com
ALLOW_OFFLINE_AGENTS=1
MEM0_USE_REMOTE=0
```

## 5. CI

GitHub Actions (`.github/workflows/ci.yml`) chạy review + pytest trên mỗi push `main`.

## 6. Checklist production

- [ ] Đổi mật khẩu demo / tắt seed admin yếu
- [ ] `POSTGRES_PASSWORD` mạnh
- [ ] HTTPS (Cloudflare / reverse proxy)
- [ ] Key VNPay/MoMo sandbox thật
- [ ] Backup Postgres
- [ ] Sentry (chưa tích hợp — optional)

## 7. Dev local (không Docker)

```powershell
cd ai-software-company
uv run uvicorn app.main:app --port 8001
# terminal 2
cd web; npm run dev
```
