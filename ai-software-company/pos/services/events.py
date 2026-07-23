from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from pos.models.events import AuditLog, OutboxEvent, OutboxStatus


def publish_event(db: Session, event_type: str, payload: dict) -> OutboxEvent:
    ev = OutboxEvent(
        event_type=event_type,
        payload=json.dumps(payload, default=str),
        status=OutboxStatus.pending,
    )
    db.add(ev)
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


def process_outbox(db: Session, limit: int = 50) -> dict:
    """Simple worker: mark events processed (hooks for CRM/analytics later)."""
    rows = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.status == OutboxStatus.pending)
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
        .all()
    )
    processed = 0
    for ev in rows:
        try:
            # side-effects placeholder: log only
            _ = json.loads(ev.payload)
            ev.status = OutboxStatus.processed
            ev.processed_at = datetime.now(UTC)
            ev.attempts += 1
            processed += 1
        except Exception as exc:
            ev.status = OutboxStatus.failed
            ev.attempts += 1
            ev.last_error = str(exc)
    db.commit()
    return {"processed": processed, "scanned": len(rows)}
