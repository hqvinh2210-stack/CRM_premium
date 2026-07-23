# Multi-stage production image: POS API + built React SPA
# Build: docker build -t crm-pos .
# Run:   docker run -p 8001:8001 --env-file .env crm-pos

# ---- Frontend build ----
FROM node:22-alpine AS web-build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- Python API ----
FROM python:3.11-slim AS api
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# uv for lockfile-consistent installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .
# Drop local junk if present (.venv is created by uv sync above — never delete it)
RUN rm -rf .data .mem0 web/node_modules || true
COPY --from=web-build /web/dist ./web/dist

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    SERVE_WEB=1 \
    USE_ALEMBIC=1 \
    OUTBOX_WORKER=1 \
    PORT=8001

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8001/health || exit 1

CMD ["sh", "-c", "alembic upgrade head || true; uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
