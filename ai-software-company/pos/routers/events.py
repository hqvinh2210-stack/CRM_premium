from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.events import OutboxEvent, OutboxStatus
from pos.services.events import process_outbox, requeue_dead_letters

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/process")
def process_events(
    limit: int = 50,
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    return process_outbox(db, limit=limit)


@router.post("/requeue-dead")
def requeue_dead(
    limit: int = 50,
    ctx: AuthContext = Depends(require_any("admin")),
    db: Session = Depends(get_db),
):
    """Ops: requeue dead_letter events for another processing pass."""
    return requeue_dead_letters(db, limit=limit)


@router.get("/outbox")
def list_outbox(
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
    limit: int = 50,
    status: str | None = Query(default=None, description="pending|processed|failed|dead_letter"),
):
    q = db.query(OutboxEvent)
    if status:
        try:
            st = OutboxStatus(status)
            q = q.filter(OutboxEvent.status == st)
        except ValueError:
            pass
    rows = q.order_by(OutboxEvent.created_at.desc()).limit(limit).all()
    return {
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "status": e.status.value,
                "attempts": e.attempts,
                "last_error": e.last_error,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "processed_at": e.processed_at.isoformat() if e.processed_at else None,
            }
            for e in rows
        ]
    }

