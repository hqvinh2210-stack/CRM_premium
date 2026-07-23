from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.crm_tasks import FollowUpTask, TaskStatus
from pos.models.customers import Customer
from pos.services.events import audit

router = APIRouter(prefix="/tasks", tags=["crm-tasks"])


class TaskCreate(BaseModel):
    customer_id: str
    title: str = Field(min_length=1, max_length=255)
    notes: str | None = None
    due_at: datetime | None = None
    assigned_to: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None
    due_at: datetime | None = None
    status: str | None = None
    assigned_to: str | None = None


def _out(t: FollowUpTask) -> dict:
    return {
        "id": t.id,
        "customer_id": t.customer_id,
        "store_id": t.store_id,
        "title": t.title,
        "notes": t.notes,
        "status": t.status.value,
        "due_at": t.due_at.isoformat() if t.due_at else None,
        "assigned_to": t.assigned_to,
        "created_by": t.created_by,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }


@router.get("")
def list_tasks(
    status: str | None = Query(default="open"),
    customer_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    q = db.query(FollowUpTask).filter(
        (FollowUpTask.store_id == ctx.store_id) | (FollowUpTask.store_id.is_(None))
    )
    if status:
        try:
            q = q.filter(FollowUpTask.status == TaskStatus(status))
        except ValueError:
            pass
    if customer_id:
        q = q.filter(FollowUpTask.customer_id == customer_id)
    rows = q.order_by(FollowUpTask.created_at.desc()).limit(limit).all()
    return {"tasks": [_out(t) for t in rows]}


@router.post("")
def create_task(
    body: TaskCreate,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    if not db.get(Customer, body.customer_id):
        raise HTTPException(404, "Customer not found")
    t = FollowUpTask(
        customer_id=body.customer_id,
        store_id=ctx.store_id,
        title=body.title,
        notes=body.notes,
        due_at=body.due_at,
        assigned_to=body.assigned_to or ctx.user.id,
        created_by=ctx.user.id,
        status=TaskStatus.open,
    )
    db.add(t)
    audit(
        db,
        actor_id=ctx.user.id,
        action="task.created",
        entity="follow_up_task",
        entity_id=None,
        detail=body.title,
    )
    db.commit()
    db.refresh(t)
    # fix entity_id after id assigned
    return _out(t)


@router.patch("/{task_id}")
def update_task(
    task_id: str,
    body: TaskUpdate,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    t = db.get(FollowUpTask, task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        try:
            st = TaskStatus(data.pop("status"))
        except ValueError as exc:
            raise HTTPException(400, "Invalid status") from exc
        t.status = st
        if st == TaskStatus.done:
            t.completed_at = datetime.now(UTC)
        elif st == TaskStatus.open:
            t.completed_at = None
    for k, v in data.items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return _out(t)
