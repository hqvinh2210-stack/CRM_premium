"""FastAPI middleware: unhandled errors → Linear agent tasks."""

from __future__ import annotations

import os
import traceback
from collections import deque
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from pipeline.linear_ops import report_pipeline_failure

# de-dupe: don't spam Linear with identical errors
_recent: deque[str] = deque(maxlen=50)


class ProductionErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            tb = traceback.format_exc()
            path = request.url.path
            key = f"{type(exc).__name__}:{path}:{str(exc)[:120]}"
            enabled = os.getenv("LINEAR_ON_PROD_ERROR", "1") not in {"0", "false", "False"}
            if enabled and key not in _recent:
                _recent.append(key)
                try:
                    report_pipeline_failure(
                        stage="production",
                        summary=f"{type(exc).__name__} on {request.method} {path}",
                        detail=(
                            f"time={datetime.now(UTC).isoformat()}\n"
                            f"method={request.method}\n"
                            f"path={path}\n"
                            f"query={request.url.query}\n\n"
                            f"{tb}"
                        ),
                        source="fastapi.middleware",
                    )
                except Exception as report_exc:
                    print(f"[error_middleware] Linear report failed: {report_exc}")
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "error": "internal_server_error",
                    "detail": str(exc),
                    "path": path,
                },
            )
