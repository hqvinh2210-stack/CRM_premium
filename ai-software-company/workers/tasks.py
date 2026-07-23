"""Celery tasks: outbox consumer + loyalty expiry."""

from __future__ import annotations

import os

from workers.celery_app import celery_app


@celery_app.task(name="workers.tasks.process_outbox_batch", bind=True, max_retries=3)
def process_outbox_batch(self, limit: int = 50) -> dict:
    from pos.db import SessionLocal
    from pos.services.events import process_outbox

    db = SessionLocal()
    try:
        result = process_outbox(db, limit=limit)
        result["via"] = "celery"
        return result
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc, countdown=10) from exc
    finally:
        db.close()


@celery_app.task(name="workers.tasks.expire_loyalty_points")
def expire_loyalty_points(ttl_days: int | None = None) -> dict:
    from pos.db import SessionLocal
    from pos.services.loyalty import expire_stale_points

    db = SessionLocal()
    try:
        days = ttl_days or int(os.getenv("POINTS_TTL_DAYS", "365"))
        result = expire_stale_points(db, ttl_days=days)
        result["via"] = "celery"
        return result
    finally:
        db.close()


@celery_app.task(name="workers.tasks.enqueue_event_hint")
def enqueue_event_hint(event_type: str, payload: dict) -> dict:
    """Optional side-path: kick outbox processing after publish."""
    async_result = process_outbox_batch.delay(limit=20)
    return {
        "queued": True,
        "task_id": async_result.id,
        "event_type": event_type,
        "payload_keys": list(payload.keys()),
    }
