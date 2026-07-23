"""Cashier shift open / close (Phase 5)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.orders import Order, OrderStatus, Payment, PaymentMethod
from pos.models.shifts import CashShift, ShiftStatus
from pos.services.events import audit

router = APIRouter(prefix="/shifts", tags=["shifts"])


class OpenShiftIn(BaseModel):
    opening_cash: Decimal = Field(default=Decimal("0"), ge=0)
    note: str | None = None


class CloseShiftIn(BaseModel):
    closing_cash: Decimal = Field(..., ge=0)
    note: str | None = None


def _shift_out(s: CashShift) -> dict:
    return {
        "id": s.id,
        "store_id": s.store_id,
        "user_id": s.user_id,
        "status": s.status.value,
        "opening_cash": str(s.opening_cash),
        "closing_cash": str(s.closing_cash) if s.closing_cash is not None else None,
        "expected_cash": str(s.expected_cash) if s.expected_cash is not None else None,
        "variance": str(s.variance) if s.variance is not None else None,
        "note": s.note,
        "opened_at": s.opened_at.isoformat() if s.opened_at else None,
        "closed_at": s.closed_at.isoformat() if s.closed_at else None,
    }


@router.get("/current")
def current_shift(
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    s = (
        db.query(CashShift)
        .filter(CashShift.store_id == ctx.store_id, CashShift.status == ShiftStatus.open)
        .order_by(CashShift.opened_at.desc())
        .first()
    )
    return {"shift": _shift_out(s) if s else None}


@router.post("/open")
def open_shift(
    body: OpenShiftIn,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(CashShift)
        .filter(CashShift.store_id == ctx.store_id, CashShift.status == ShiftStatus.open)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Store already has an open shift")

    s = CashShift(
        store_id=ctx.store_id,
        user_id=ctx.user.id,
        status=ShiftStatus.open,
        opening_cash=body.opening_cash,
        note=body.note,
    )
    db.add(s)
    audit(
        db,
        actor_id=ctx.user.id,
        action="shift.open",
        entity="cash_shift",
        entity_id=s.id,
        detail=f"opening_cash={body.opening_cash}",
    )
    db.commit()
    db.refresh(s)
    return _shift_out(s)


@router.post("/{shift_id}/close")
def close_shift(
    shift_id: str,
    body: CloseShiftIn,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    s = db.get(CashShift, shift_id)
    if not s or s.store_id != ctx.store_id:
        raise HTTPException(status_code=404, detail="Shift not found")
    if s.status != ShiftStatus.open:
        raise HTTPException(status_code=400, detail="Shift already closed")

    # Expected = opening + cash payments since open
    opened = s.opened_at or datetime.now(UTC)
    cash_sales = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Order, Order.id == Payment.order_id)
        .filter(
            Order.store_id == ctx.store_id,
            Order.status == OrderStatus.paid,
            Order.paid_at >= opened,
            Payment.method == PaymentMethod.cash,
        )
        .scalar()
        or 0
    )
    expected = (s.opening_cash + Decimal(str(cash_sales))).quantize(Decimal("0.01"))
    variance = (body.closing_cash - expected).quantize(Decimal("0.01"))

    s.status = ShiftStatus.closed
    s.closing_cash = body.closing_cash
    s.expected_cash = expected
    s.variance = variance
    s.closed_at = datetime.now(UTC)
    if body.note:
        s.note = ((s.note or "") + " | close: " + body.note).strip(" |")
    db.add(s)
    audit(
        db,
        actor_id=ctx.user.id,
        action="shift.close",
        entity="cash_shift",
        entity_id=s.id,
        detail=f"closing={body.closing_cash} expected={expected} variance={variance}",
    )
    db.commit()
    db.refresh(s)
    return _shift_out(s)


@router.get("")
def list_shifts(
    ctx: AuthContext = Depends(require_any("manager", "admin", "cashier")),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(CashShift)
        .filter(CashShift.store_id == ctx.store_id)
        .order_by(CashShift.opened_at.desc())
        .limit(30)
        .all()
    )
    return {"shifts": [_shift_out(s) for s in rows]}
