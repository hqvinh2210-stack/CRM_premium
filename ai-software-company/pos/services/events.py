from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from pos.models.events import AuditLog, OutboxEvent, OutboxStatus

# Max attempts before dead-letter. Override with OUTBOX_MAX_ATTEMPTS.
DEFAULT_MAX_ATTEMPTS = int(os.getenv("OUTBOX_MAX_ATTEMPTS", "5"))


def publish_event(db: Session, event_type: str, payload: dict) -> OutboxEvent:
    ev = OutboxEvent(
        event_type=event_type,
        payload=json.dumps(payload, default=str),
        status=OutboxStatus.pending,
    )
    db.add(ev)
    # Best-effort Celery kick (does not require commit yet)
    if os.getenv("CELERY_ENABLED", "0") == "1" and os.getenv("CELERY_ON_PUBLISH", "1") == "1":
        try:
            from workers.tasks import process_outbox_batch

            process_outbox_batch.delay(limit=20)
        except Exception:
            pass
    return ev


def audit(
    db: Session,
    *,
    actor_id: str | None,
    action: str,
    entity: str | None = None,
    entity_id: str | None = None,
    detail: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            detail=detail,
        )
    )


def _dispatch_event(event_type: str, payload: dict) -> None:
    """
    In-process handlers (local worker; Celery optional later).
    Raise to trigger retry / DLQ.
    """
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid payload for {event_type}")

    # Wire LangGraph agents on order events (P3-M4-T4)
    if event_type in {"order.created", "order.refunded"}:
        from pos.services.ai_events import agent_on_order_enabled, queue_or_run_agent

        if agent_on_order_enabled():
            # Prefer queue; do not fail outbox on agent errors unless strict
            result = queue_or_run_agent(event_type, payload)
            if (
                os.getenv("AGENT_ON_ORDER_STRICT", "0") == "1"
                and not result.get("ok")
                and not result.get("skipped")
            ):
                raise RuntimeError(result.get("error") or "agent failed")

    return


def process_outbox(
    db: Session,
    limit: int = 50,
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    include_failed: bool = True,
) -> dict:
    """
    Worker with retry + dead-letter:
      pending (and optionally failed with attempts < max) → process
      on hard fail after max_attempts → dead_letter
    """
    statuses = [OutboxStatus.pending]
    if include_failed:
        statuses.append(OutboxStatus.failed)

    rows = (
        db.query(OutboxEvent)
        .filter(
            OutboxEvent.status.in_(statuses),
            OutboxEvent.attempts < max_attempts,
        )
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
        .all()
    )
    processed = 0
    failed = 0
    dead_lettered = 0
    for ev in rows:
        try:
            payload = json.loads(ev.payload)
            _dispatch_event(ev.event_type, payload)
            ev.status = OutboxStatus.processed
            ev.processed_at = datetime.now(UTC)
            ev.attempts += 1
            ev.last_error = None
            processed += 1
        except Exception as exc:
            ev.attempts += 1
            ev.last_error = str(exc)[:2000]
            if ev.attempts >= max_attempts:
                ev.status = OutboxStatus.dead_letter
                dead_lettered += 1
            else:
                ev.status = OutboxStatus.failed
                failed += 1
    db.commit()
    return {
        "processed": processed,
        "failed": failed,
        "dead_lettered": dead_lettered,
        "scanned": len(rows),
        "max_attempts": max_attempts,
    }


def requeue_dead_letters(db: Session, limit: int = 50) -> dict:
    """Move dead_letter events back to pending (manual ops)."""
    rows = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.status == OutboxStatus.dead_letter)
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
        .all()
    )
    for ev in rows:
        ev.status = OutboxStatus.pending
        ev.attempts = 0
        ev.last_error = None
    db.commit()
    return {"requeued": len(rows)}
