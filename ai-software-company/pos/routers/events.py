from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.events import OutboxEvent
from pos.services.events import process_outbox

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/process")
def process_events(
    limit: int = 50,
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    return process_outbox(db, limit=limit)


@router.get("/outbox")
def list_outbox(
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    rows = db.query(OutboxEvent).order_by(OutboxEvent.created_at.desc()).limit(limit).all()
    return {
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "status": e.status.value,
                "attempts": e.attempts,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in rows
        ]
    }
