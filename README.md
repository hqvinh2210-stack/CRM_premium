# CRM_premium

AI Software Company + Linear webhook orchestrator.

## Projects

- `ai-software-company/` — FastAPI + LangGraph (Phase 1–4)
- `orchestrator/` — Linear webhook receiver (ngrok)

## Quick start

### AI Software Company

```powershell
cd ai-software-company
uv sync
uv run uvicorn app.main:app --reload --port 8001
uv run python -m graph.graph
```

### Linear orchestrator

```powershell
cd orchestrator
uv sync
uv run uvicorn main:app --reload --port 8000
# ngrok http 8000
```
