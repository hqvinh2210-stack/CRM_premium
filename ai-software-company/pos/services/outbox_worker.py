"""Outbox worker: Celery (Redis) preferred, in-process thread fallback."""

from __future__ import annotations

import os
import threading
import time
from typing import Any

_worker_started = False
_stop = threading.Event()
_stats: dict[str, Any] = {
    "runs": 0,
    "last_result": None,
    "last_at": None,
    "mode": "none",
}


def worker_stats() -> dict[str, Any]:
    return dict(_stats)


def celery_enabled() -> bool:
    return os.getenv("CELERY_ENABLED", "0") == "1"


def redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")


def try_enqueue_outbox(limit: int = 50) -> dict | None:
    """Enqueue Celery task if enabled; return None if unavailable."""
    if not celery_enabled():
        return None
    try:
        from workers.tasks import process_outbox_batch

        async_result = process_outbox_batch.delay(limit)
        _stats["mode"] = "celery"
        _stats["last_enqueue"] = async_result.id
        return {"enqueued": True, "task_id": async_result.id, "mode": "celery"}
    except Exception as exc:  # noqa: BLE001
        _stats["celery_error"] = str(exc)
        return None


def _loop(interval: float) -> None:
    from pos.db import SessionLocal
    from pos.services.events import process_outbox

    while not _stop.is_set():
        # Prefer pushing work to Celery if enabled
        if celery_enabled():
            enq = try_enqueue_outbox(limit=50)
            if enq:
                _stats["runs"] += 1
                _stats["last_result"] = enq
                _stats["last_at"] = time.time()
                _stop.wait(interval)
                continue

        db = SessionLocal()
        try:
            result = process_outbox(db, limit=50)
            result["via"] = "thread"
            _stats["runs"] += 1
            _stats["last_result"] = result
            _stats["last_at"] = time.time()
            _stats["mode"] = "thread"
        except Exception as exc:  # noqa: BLE001
            _stats["last_error"] = str(exc)
        finally:
            db.close()
        _stop.wait(interval)


def start_outbox_worker() -> bool:
    """
    Start background poller if OUTBOX_WORKER=1 (default).
    When CELERY_ENABLED=1, poller enqueues Celery tasks (worker process must run).
    When Celery unavailable, falls back to in-process process_outbox.
    """
    global _worker_started
    if _worker_started:
        return False
    if os.getenv("OUTBOX_WORKER", "1") != "1":
        _stats["mode"] = "disabled"
        return False

    # Probe redis/celery once
    if celery_enabled():
        try:
            import redis

            r = redis.Redis.from_url(redis_url(), socket_connect_timeout=1)
            r.ping()
            _stats["redis"] = "ok"
            _stats["mode"] = "celery"
        except Exception as exc:  # noqa: BLE001
            _stats["redis"] = f"unavailable: {exc}"
            _stats["mode"] = "thread_fallback"
            print(f"[outbox] Redis unavailable, using in-process worker: {exc}")

    interval = float(os.getenv("OUTBOX_WORKER_INTERVAL", "15"))
    t = threading.Thread(target=_loop, args=(interval,), name="outbox-worker", daemon=True)
    t.start()
    _worker_started = True
    return True


def stop_outbox_worker() -> None:
    _stop.set()
