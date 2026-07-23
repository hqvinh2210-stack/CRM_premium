"""Phase 5 ops: metrics, audit trail, backup, staff list."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.auth import User, UserStoreRole
from pos.models.catalog import Product, StockLevel
from pos.models.customers import Customer
from pos.models.events import AuditLog, OutboxEvent, OutboxStatus
from pos.models.orders import Order, OrderStatus, Payment, PaymentMethod
from pos.models.shifts import CashShift, ShiftStatus
from pos.services.events import audit

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/metrics")
def ops_metrics(
    ctx: AuthContext = Depends(require_any("manager", "admin", "cashier")),
    db: Session = Depends(get_db),
):
    """Live store metrics for SoftPOS dashboard (P5-M1)."""
    today = date.today()
    start = datetime.combine(today, time.min)
    end = datetime.combine(today, time.max)

    paid_q = db.query(Order).filter(
        Order.store_id == ctx.store_id,
        Order.status == OrderStatus.paid,
        Order.paid_at >= start,
        Order.paid_at <= end,
    )
    orders_today = paid_q.count()
    revenue = paid_q.with_entities(func.coalesce(func.sum(Order.total), 0)).scalar() or 0

    cash_today = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Order, Order.id == Payment.order_id)
        .filter(
            Order.store_id == ctx.store_id,
            Order.status == OrderStatus.paid,
            Order.paid_at >= start,
            Order.paid_at <= end,
            Payment.method == PaymentMethod.cash,
        )
        .scalar()
        or 0
    )

    open_shift = (
        db.query(CashShift)
        .filter(
            CashShift.store_id == ctx.store_id,
            CashShift.status == ShiftStatus.open,
        )
        .order_by(CashShift.opened_at.desc())
        .first()
    )

    outbox_pending = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.status.in_([OutboxStatus.pending, OutboxStatus.failed]))
        .count()
    )
    outbox_dlq = (
        db.query(OutboxEvent).filter(OutboxEvent.status == OutboxStatus.dead_letter).count()
    )

    low_stock = (
        db.query(StockLevel)
        .join(Product, Product.id == StockLevel.product_id)
        .filter(
            StockLevel.store_id == ctx.store_id,
            Product.track_inventory.is_(True),
            Product.deleted_at.is_(None),
            StockLevel.qty <= 10,
        )
        .count()
    )

    customers = db.query(Customer).count()

    return {
        "store_id": ctx.store_id,
        "date": today.isoformat(),
        "orders_today": orders_today,
        "revenue_today": str(Decimal(revenue).quantize(Decimal("0.01"))),
        "cash_sales_today": str(Decimal(cash_today).quantize(Decimal("0.01"))),
        "customers_total": customers,
        "low_stock_skus": low_stock,
        "outbox": {"pending_or_failed": outbox_pending, "dead_letter": outbox_dlq},
        "shift": (
            {
                "id": open_shift.id,
                "status": open_shift.status.value,
                "opening_cash": str(open_shift.opening_cash),
                "opened_at": open_shift.opened_at.isoformat() if open_shift.opened_at else None,
                "user_id": open_shift.user_id,
            }
            if open_shift
            else None
        ),
        "generated_at": datetime.now(UTC).isoformat(),
    }


@router.get("/audit")
def list_audit(
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = None,
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    """Recent audit log (P5 admin)."""
    q = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        q = q.filter(AuditLog.action == action)
    rows = q.limit(limit).all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": a.id,
                "actor_id": a.actor_id,
                "action": a.action,
                "entity": a.entity,
                "entity_id": a.entity_id,
                "detail": a.detail,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ],
    }


@router.get("/staff")
def list_staff(
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    """Staff with roles in current store."""
    links = (
        db.query(UserStoreRole, User)
        .join(User, User.id == UserStoreRole.user_id)
        .filter(UserStoreRole.store_id == ctx.store_id)
        .all()
    )
    return {
        "store_id": ctx.store_id,
        "staff": [
            {
                "user_id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "phone": u.phone,
                "role": link.role.value if hasattr(link.role, "value") else str(link.role),
                "is_active": u.is_active,
            }
            for link, u in links
        ],
    }


@router.get("/backup.json")
def backup_json(
    ctx: AuthContext = Depends(require_any("admin")),
    db: Session = Depends(get_db),
):
    """
    Lightweight store-scoped JSON backup (P5-M2).
    Not a full DB dump — key tables for disaster recovery / staging seed.
    """
    from pos.models.catalog import Category

    products = (
        db.query(Product)
        .filter(Product.deleted_at.is_(None))
        .limit(5000)
        .all()
    )
    stock = db.query(StockLevel).filter(StockLevel.store_id == ctx.store_id).all()
    customers = db.query(Customer).limit(5000).all()
    since = datetime.now(UTC) - timedelta(days=30)
    orders = (
        db.query(Order)
        .filter(Order.store_id == ctx.store_id, Order.created_at >= since)
        .limit(2000)
        .all()
    )

    payload = {
        "version": "0.8.0",
        "store_id": ctx.store_id,
        "exported_at": datetime.now(UTC).isoformat(),
        "exported_by": ctx.user.email,
        "products": [
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "price": str(p.price),
                "barcode": p.barcode,
            }
            for p in products
        ],
        "stock_levels": [
            {"product_id": s.product_id, "qty": s.qty, "version": getattr(s, "version", None)}
            for s in stock
        ],
        "customers": [
            {"id": c.id, "phone": c.phone, "name": c.name, "email": c.email}
            for c in customers
        ],
        "orders_30d": [
            {
                "id": o.id,
                "status": o.status.value,
                "total": str(o.total),
                "paid_at": o.paid_at.isoformat() if o.paid_at else None,
                "customer_id": o.customer_id,
            }
            for o in orders
        ],
        "categories": [
            {"id": c.id, "name": c.name} for c in db.query(Category).limit(500).all()
        ],
    }
    audit(
        db,
        actor_id=ctx.user.id,
        action="ops.backup",
        entity="store",
        entity_id=ctx.store_id,
        detail=f"orders={len(orders)} products={len(products)}",
    )
    db.commit()

    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return StreamingResponse(
        iter([data]),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="crm_backup_{ctx.store_id[:8]}.json"'
        },
    )
