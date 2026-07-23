# AI Software Company

Multi-agent software company scaffold (FastAPI + LangGraph).

## Setup

```powershell
cd C:\Users\admin\Downloads\CRM\ai-software-company
.venv\Scripts\activate
```

## Phase 2 — FastAPI

```powershell
uv run uvicorn app.main:app --reload --port 8001
```

Open http://localhost:8001 → `{"status":"running"}`

> Port **8001** mặc định ở đây để không đụng orchestrator Linear webhook (port 8000).

## Phase 3–4 — LangGraph

```powershell
uv run python -m graph.graph
```

Console in: `Create Login API`

## Structure

```text
ai-software-company/
  app/          # FastAPI
  graph/        # LangGraph state + graph
  agents/       # (later)
  tools/        # (later)
  config/       # (later)
  tests/
  docs/
```

## Packages (installed)

fastapi, uvicorn, langgraph, langchain, langchain-openai, langchain-community, pydantic, python-dotenv

Chưa cài: Mem0, Redis, PostgreSQL.
