from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents.roles import list_roles
from app.linear import handle_linear_webhook
from config.settings import get_settings
from graph.graph import graph
from memory.service import get_memory_service
from pipeline.error_middleware import ProductionErrorMiddleware
from pos.bootstrap import bootstrap_pos
from pos.middleware_rate_limit import RateLimitMiddleware
from pos.routers import api_router as pos_api_router
from pos.services.outbox_worker import start_outbox_worker, stop_outbox_worker, worker_stats

ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = ROOT / "web" / "dist"
SERVE_WEB = os.getenv("SERVE_WEB", "0") == "1" and WEB_DIST.is_dir()


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw == "*":
        return ["*"]
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
    ]


def _init_sentry() -> None:
    """Optional Sentry (P4-M4). Set SENTRY_DSN to enable."""
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            environment=os.getenv("SENTRY_ENV", "local"),
            integrations=[StarletteIntegration(), FastApiIntegration()],
        )
        print("[ops] Sentry enabled")
    except Exception as exc:  # noqa: BLE001
        print(f"[ops] Sentry init skipped: {exc}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _init_sentry()
    info = bootstrap_pos()
    started = start_outbox_worker()
    print(f"[pos] DB ready. Demo login: {info['admin_email']} / {info['admin_password']}")
    print(f"[pos] store_id={info['store_id']}")
    print(f"[pos] outbox worker started={started}")
    print(f"[pos] serve_web={SERVE_WEB} dist={WEB_DIST}")
    yield
    stop_outbox_worker()


app = FastAPI(title="AI Software Company + POS CRM", version="0.8.0", lifespan=lifespan)
_origins = _cors_origins()
# Explicit Pages + local origins (avoids browser quirks with bare "*")
_DEFAULT_EXTRA = [
    "https://hqvinh2210-stack.github.io",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
]
if _origins == ["*"]:
    # With credentials=false, * is fine; also list known origins for PNA + debugging
    _cors_list = ["*"]
else:
    _cors_list = list(dict.fromkeys(_origins + _DEFAULT_EXTRA))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_list,
    allow_credentials=_cors_list != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.add_middleware(ProductionErrorMiddleware)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def private_network_and_cors_fix(request: Request, call_next):
    """
    Chrome Private Network Access: public HTTPS (GitHub Pages) → localhost API.
    Preflight sends Access-Control-Request-Private-Network: true.
    """
    if request.method == "OPTIONS" and request.headers.get(
        "access-control-request-private-network"
    ):
        origin = request.headers.get("origin", "*")
        return JSONResponse(
            content={},
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": origin if origin else "*",
                "Access-Control-Allow-Methods": "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT",
                "Access-Control-Allow-Headers": request.headers.get(
                    "access-control-request-headers", "*"
                ),
                "Access-Control-Allow-Private-Network": "true",
                "Access-Control-Max-Age": "600",
                "Vary": "Origin",
            },
        )

    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    # Ensure CORS on error responses too when * is configured
    origin = request.headers.get("origin")
    if origin and "access-control-allow-origin" not in {
        k.lower() for k in response.headers.keys()
    }:
        if _cors_list == ["*"] or origin in _cors_list:
            response.headers["Access-Control-Allow-Origin"] = (
                "*" if _cors_list == ["*"] else origin
            )
    return response


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


@app.get("/api")
async def api_root():
    """JSON root when SPA occupies `/` in production (SERVE_WEB=1)."""
    return {
        "status": "running",
        "product": "POS + CRM (Phase 1–4) + AI agents",
        "version": "0.8.0",
        "agents": "memory → planner(Ava) → coder(Rex) → reviewer(Kai)",
        "pos_api": "/api/v1/*",
        "docs": "/docs",
        "ui": "/" if SERVE_WEB else "http://127.0.0.1:5173",
        "endpoints": {
            "health": "GET /health",
            "pos_login": "POST /api/v1/auth/login",
            "pos_products": "GET /api/v1/products",
            "pos_orders": "POST /api/v1/orders",
            "ops_metrics": "GET /api/v1/ops/metrics",
            "shifts": "POST /api/v1/shifts/open",
            "export_xlsx": "GET /api/v1/reports/export.xlsx",
            "roles": "GET /agents/roles",
            "run": "POST /run",
            "memory": "GET /memory",
            "linear": "POST /linear",
        },
    }


@app.get("/")
async def root():
    if SERVE_WEB:
        index = WEB_DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
    return await api_root()


@app.get("/health")
async def health():
    settings = get_settings()
    mem = get_memory_service()
    return {
        "ok": True,
        "graph": "memory → planner → coding → review",
        "pos": "phase1-5-ops",
        "version": "0.8.0",
        "agent_on_order": os.getenv("AGENT_ON_ORDER", "0") == "1",
        "sentry": bool(os.getenv("SENTRY_DSN")),
        "db_backend": __import__("pos.db", fromlist=["db_backend"]).db_backend(),
        "outbox_worker": worker_stats(),
        "celery_enabled": __import__("os").getenv("CELERY_ENABLED", "0") == "1",
        "llm_enabled": settings.llm_enabled and not settings.force_offline,
        "model": (
            (settings.xai_model if settings.xai_api_key else settings.gemini_model)
            if settings.llm_enabled and not settings.force_offline
            else None
        ),
        "mode": (
            "offline"
            if settings.force_offline or not settings.llm_enabled
            else ("xai" if settings.xai_api_key else "gemini")
        ),
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


# ---- Production SPA (React build in web/dist) ----
if SERVE_WEB:
    assets = WEB_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str, request: Request):
        """Serve static files or index.html for client-side routes."""
        # Never swallow API / docs / health
        blocked = (
            "api/",
            "docs",
            "redoc",
            "openapi.json",
            "health",
            "run",
            "memory",
            "linear",
            "agents",
            "pipeline",
        )
        if full_path == "api" or any(
            full_path == b or full_path.startswith(b if b.endswith("/") else b + "/")
            or full_path.startswith(b)
            for b in blocked
        ):
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        candidate = WEB_DIST / full_path
        if candidate.is_file() and candidate.resolve().is_relative_to(WEB_DIST.resolve()):
            return FileResponse(candidate)
        index = WEB_DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse({"detail": "SPA not built"}, status_code=404)
