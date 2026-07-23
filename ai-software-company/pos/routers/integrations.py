from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.integrations import EInvoice, NotificationLog
from pos.models.orders import Order, OrderStatus
from pos.services.einvoice import issue_einvoice
from pos.services.events import audit, publish_event
from pos.services.notify import queue_order_notify

router = APIRouter(tags=["integrations"])


class EInvoiceIn(BaseModel):
    order_id: str
    tax_code: str | None = None
    buyer_name: str | None = None


@router.post("/invoices/e-invoice")
def create_einvoice(
    body: EInvoiceIn,
    ctx: AuthContext = Depends(require_any("manager", "admin", "cashier")),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == body.order_id, Order.store_id == ctx.store_id)
        .first()
    )
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status not in {OrderStatus.paid, OrderStatus.refunded}:
        raise HTTPException(400, "Order must be paid or refunded")
    inv = issue_einvoice(db, order, tax_code=body.tax_code, buyer_name=body.buyer_name)
    publish_event(
        db,
        "invoice.issued",
        {"invoice_id": inv.id, "order_id": order.id, "invoice_no": inv.invoice_no},
    )
    audit(
        db,
        actor_id=ctx.user.id,
        action="invoice.issued",
        entity="e_invoice",
        entity_id=inv.id,
        detail=inv.invoice_no,
    )
    db.commit()
    return {
        "id": inv.id,
        "invoice_no": inv.invoice_no,
        "status": inv.status.value,
        "order_id": inv.order_id,
        "tax_code": inv.tax_code,
        "buyer_name": inv.buyer_name,
        "payload": json.loads(inv.payload) if inv.payload else None,
    }


@router.get("/invoices/e-invoice/{invoice_id}")
def get_einvoice(
    invoice_id: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    inv = db.get(EInvoice, invoice_id)
    if not inv or inv.store_id != ctx.store_id:
        raise HTTPException(404, "Not found")
    return {
        "id": inv.id,
        "invoice_no": inv.invoice_no,
        "status": inv.status.value,
        "order_id": inv.order_id,
        "payload": json.loads(inv.payload) if inv.payload else None,
    }


class NotifyIn(BaseModel):
    order_id: str
    phone: str | None = None
    channel: str = Field(default="sms", description="sms|zalo")


@router.post("/notify/order")
def notify_order(
    body: NotifyIn,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == body.order_id, Order.store_id == ctx.store_id)
        .first()
    )
    if not order:
        raise HTTPException(404, "Order not found")
    import os

    os.environ["NOTIFY_CHANNEL"] = body.channel
    log = queue_order_notify(db, order, phone=body.phone)
    if not log:
        raise HTTPException(400, "No recipient phone")
    db.commit()
    db.refresh(log)
    return {
        "id": log.id,
        "channel": log.channel.value,
        "recipient": log.recipient,
        "status": log.status.value,
        "body": log.body,
    }


@router.get("/notify/logs")
def list_notify_logs(
    limit: int = 50,
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    rows = db.query(NotificationLog).order_by(NotificationLog.created_at.desc()).limit(limit).all()
    return {
        "logs": [
            {
                "id": r.id,
                "channel": r.channel.value,
                "recipient": r.recipient,
                "status": r.status.value,
                "template": r.template,
                "ref_id": r.ref_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }
