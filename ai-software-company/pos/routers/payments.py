from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.routers.orders import _load_order
from pos.models.orders import PaymentMethod
from pos.services.orders import atomic_pay

router = APIRouter(prefix="/payments", tags=["payments"])


class IntentIn(BaseModel):
    order_id: str
    provider: str = Field(description="vnpay|momo|zalopay|cash")
    return_url: str | None = None


@router.post("/intent")
def create_payment_intent(
    body: IntentIn,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    """Sandbox payment intent (Phase 3 stub for VN gateways)."""
    order = _load_order(db, body.order_id, ctx.store_id)
    provider = body.provider.lower()
    if provider not in {"vnpay", "momo", "zalopay", "cash"}:
        raise HTTPException(400, "Unsupported provider")

    intent_id = str(uuid.uuid4())
    if provider == "cash":
        paid = atomic_pay(
            db,
            order,
            method=PaymentMethod.cash,
            amount=order.total,
            ref=f"cash:{intent_id}",
            idempotency_key=f"intent:{intent_id}",
        )
        return {
            "provider": "cash",
            "intent_id": intent_id,
            "status": "captured",
            "order_id": paid.id,
            "amount": str(paid.total),
        }

    # e-wallet: return fake redirect URL (sandbox)
    return {
        "provider": provider,
        "intent_id": intent_id,
        "status": "requires_action",
        "amount": str(order.total),
        "order_id": order.id,
        "checkout_url": f"https://sandbox.{provider}.vn/pay/{intent_id}?amount={order.total}",
        "message": "Sandbox only — complete capture via /payments/capture",
    }


class CaptureIn(BaseModel):
    intent_id: str
    order_id: str
    provider: str


@router.post("/capture")
def capture_payment(
    body: CaptureIn,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    order = _load_order(db, body.order_id, ctx.store_id)
    method = PaymentMethod.ewallet if body.provider != "cash" else PaymentMethod.cash
    paid = atomic_pay(
        db,
        order,
        method=method,
        amount=order.total,
        ref=f"{body.provider}:{body.intent_id}",
        idempotency_key=f"intent:{body.intent_id}",
    )
    return {"status": "captured", "order_id": paid.id, "total": str(paid.total)}
