from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.roles import list_roles
from app.linear import handle_linear_webhook
from config.settings import get_settings
from graph.graph import graph
from memory.service import get_memory_service
from pipeline.error_middleware import ProductionErrorMiddleware
from pos.bootstrap import bootstrap_pos
from pos.routers import api_router as pos_api_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    info = bootstrap_pos()
    print(f"[pos] DB ready. Demo login: {info['admin_email']} / {info['admin_password']}")
    print(f"[pos] store_id={info['store_id']}")
    yield


app = FastAPI(title="AI Software Company + POS CRM", version="0.4.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ProductionErrorMiddleware)
app.include_router(pos_api_router)

_last_linear_result: dict | None = None


class RunRequest(BaseModel):
    task: str = Field(..., min_length=1, examples=["Create Login API"])
    issue_id: str | None = None


class RunResponse(BaseModel):
    task: str
    plan: str = ""
    code: str = ""
    review: str = ""
    status: str = ""
    logs: list[str] = Field(default_factory=list)
    agent_modes: dict = Field(default_factory=dict)
    run_id: str | None = None
    memory_hits: list = Field(default_factory=list)
    memory_context: str = ""


class MemoryAddRequest(BaseModel):
    text: str = Field(..., min_length=1)
    agent_id: str | None = Field(default="human")
    issue_id: str | None = None


@app.get("/")
async def root():
    return {
        "status": "running",
        "product": "POS + CRM MVP (Phase 1) + AI agents",
        "agents": "memory → planner(Ava) → coder(Rex) → reviewer(Kai)",
        "pos_api": "/api/v1/*",
        "docs": "/docs",
        "endpoints": {
            "health": "GET /health",
            "pos_login": "POST /api/v1/auth/login",
            "pos_products": "GET /api/v1/products",
            "pos_orders": "POST /api/v1/orders",
            "roles": "GET /agents/roles",
            "run": "POST /run",
            "memory": "GET /memory",
            "linear": "POST /linear",
        },
    }


@app.get("/health")
async def health():
    settings = get_settings()
    mem = get_memory_service()
    return {
        "ok": True,
        "graph": "memory → planner → coding → review",
        "pos": "phase1-mvp",
        "llm_enabled": settings.llm_enabled,
        "model": settings.xai_model if settings.llm_enabled else None,
        "mode": "llm" if settings.llm_enabled else "offline",
        "memory_backend": mem.backend,
        "memory_provider": settings.mem0_provider if mem.mem0_enabled else "local",
        "memory_user_id": mem.user_id,
        "linear": "POST /linear (Issue create → agents + memory)",
        "delivery_loop": "code→review→test→deploy→monitor",
    }


@app.get("/pipeline/status")
async def pipeline_status():
    """Latest delivery-loop run report (if any)."""
    from pathlib import Path
    import json

    runs = Path(__file__).resolve().parent.parent / ".data" / "pipeline_runs"
    if not runs.exists():
        return {"ok": True, "latest": None}
    files = sorted(runs.glob("run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return {"ok": True, "latest": None}
    data = json.loads(files[0].read_text(encoding="utf-8"))
    return {"ok": True, "latest_file": files[0].name, "latest": data}


@app.post("/pipeline/run")
async def pipeline_run_api(
    start_from: str = "review",
    skip_monitor: bool = False,
    open_linear_on_fail: bool = True,
):
    """Trigger delivery loop (sync — may take ~1 min for tests)."""
    from pipeline.runner import run_pipeline

    run = run_pipeline(
        start_from=start_from,
        skip_monitor=skip_monitor,
        open_linear_on_fail=open_linear_on_fail,
        health_url="http://127.0.0.1:8001/health",
    )
    return run.to_dict()


@app.get("/agents/roles")
async def agent_roles():
    return {"roles": list_roles()}


@app.post("/run", response_model=RunResponse)
async def run_pipeline(body: RunRequest):
    payload = {"task": body.task, "logs": []}
    if body.issue_id:
        payload["issue_id"] = body.issue_id
    result = graph.invoke(payload)
    return RunResponse(
        task=result.get("task", body.task),
        plan=result.get("plan", ""),
        code=result.get("code", ""),
        review=result.get("review", ""),
        status=result.get("status", ""),
        logs=result.get("logs", []),
        agent_modes=result.get("agent_modes") or {},
        run_id=result.get("run_id"),
        memory_hits=result.get("memory_hits") or [],
        memory_context=result.get("memory_context") or "",
    )


@app.get("/memory")
async def memory_list():
    mem = get_memory_service()
    items = mem.list_all()
    return {"ok": True, "backend": mem.backend, "count": len(items), "items": items}


@app.get("/memory/search")
async def memory_search(q: str = Query(..., min_length=1), top_k: int = 5):
    mem = get_memory_service()
    hits = mem.recall(q, top_k=top_k)
    return {
        "ok": True,
        "backend": mem.backend,
        "query": q,
        "hits": hits,
        "context": mem.format_context(hits),
    }


@app.post("/memory")
async def memory_add(body: MemoryAddRequest):
    mem = get_memory_service()
    return mem.remember(
        body.text,
        agent_id=body.agent_id,
        issue_id=body.issue_id,
        metadata={"kind": "manual"},
    )


@app.delete("/memory")
async def memory_clear():
    mem = get_memory_service()
    return {"ok": True, "removed": mem.clear()}


@app.post("/linear")
async def linear_webhook(data: dict):
    global _last_linear_result
    result = handle_linear_webhook(data)
    if result.get("handled"):
        _last_linear_result = result
    return result


@app.get("/linear/last")
async def linear_last():
    if _last_linear_result is None:
        return {"ok": True, "result": None, "message": "no Linear issue handled yet"}
    return {"ok": True, "result": _last_linear_result}
