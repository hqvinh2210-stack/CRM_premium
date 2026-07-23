"""Simple in-memory rate limit (P4-M3)."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, limit: int | None = None, window_s: int | None = None):
        super().__init__(app)
        self.limit = limit or int(os.getenv("RATE_LIMIT_PER_MIN", "120"))
        self.window_s = window_s or int(os.getenv("RATE_LIMIT_WINDOW_S", "60"))
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self.enabled = os.getenv("RATE_LIMIT_ENABLED", "1") == "1"

    def _key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        ip = (forwarded.split(",")[0].strip() if forwarded else None) or (
            request.client.host if request.client else "unknown"
        )
        return f"{ip}:{request.url.path}"

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)
        # skip health/docs
        path = request.url.path
        if path in {"/", "/health", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        now = time.time()
        key = self._key(request)
        q = self._hits[key]
        while q and now - q[0] > self.window_s:
            q.popleft()
        if len(q) >= self.limit:
            return JSONResponse(
                {"detail": "Rate limit exceeded", "limit": self.limit, "window_s": self.window_s},
                status_code=429,
            )
        q.append(now)
        return await call_next(request)
