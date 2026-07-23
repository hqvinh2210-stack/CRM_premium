from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.customers import Customer
from pos.models.orders import Order, OrderStatus
from pos.schemas import CustomerCreate, CustomerOut, CustomerUpdate, OrderOut
from pos.utils import normalize_vn_phone

router = APIRouter(prefix="/customers")


@router.get("", response_model=list[CustomerOut])
def list_customers(
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    """List / search customers for CRM directory."""
    query = db.query(Customer).order_by(Customer.created_at.desc())
    if q and q.strip():
        phone = normalize_vn_phone(q)
        like = f"%{q.strip()}%"
        query = query.filter(or_(Customer.phone.contains(phone), Customer.name.ilike(like)))
    return query.limit(limit).all()


@router.get("/search", response_model=list[CustomerOut])
def search_customers(
    q: str = Query(..., min_length=1),
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    return list_customers(q=q, limit=20, ctx=ctx, db=db)


@router.get("/{customer_id}/profile")
def customer_profile(
    customer_id: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    """CRM 360 profile: customer + points + paid orders + simple segment."""
    from datetime import datetime
    from decimal import Decimal

    from pos.services.loyalty import get_or_create_balance

    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Not found")

    from sqlalchemy.orm import joinedload

    orders = (
        db.query(Order)
        .options(joinedload(Order.lines))
        .filter(
            Order.customer_id == customer_id,
            Order.store_id == ctx.store_id,
            Order.status == OrderStatus.paid,
        )
        .order_by(Order.paid_at.desc())
        .limit(30)
        .all()
    )
    bal = get_or_create_balance(db, customer_id)
    db.commit()

    total_spend = sum((o.total for o in orders), Decimal("0"))
    last = orders[0].paid_at if orders else None
    recency_days = None
    if last:
        recency_days = (datetime.utcnow() - last.replace(tzinfo=None)).days
    frequency = len(orders)
    if frequency == 0:
        segment = "New"
    elif recency_days is not None and recency_days <= 30 and frequency >= 3:
        segment = "Champions"
    elif recency_days is not None and recency_days > 90:
        segment = "At Risk"
    elif frequency >= 2:
        segment = "Loyal"
    else:
        segment = "Potential"

    return {
        "customer": CustomerOut.model_validate(c).model_dump(),
        "points": {
            "balance": bal.balance,
            "lifetime_earned": bal.lifetime_earned,
        },
        "stats": {
            "order_count": frequency,
            "total_spend": str(total_spend),
            "last_purchase": last.isoformat() if last else None,
            "recency_days": recency_days,
            "segment": segment,
        },
        "orders": [
            {
                "id": o.id,
                "total": str(o.total),
                "status": o.status.value,
                "paid_at": o.paid_at.isoformat() if o.paid_at else None,
                "lines": [
                    {
                        "product_name": ln.product_name,
                        "qty": ln.qty,
                        "line_total": str(ln.line_total),
                    }
                    for ln in o.lines
                ],
            }
            for o in orders
        ],
    }


@router.post("", response_model=CustomerOut)
def create_customer(
    body: CustomerCreate,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    phone = normalize_vn_phone(body.phone)
    if db.query(Customer).filter(Customer.phone == phone).first():
        raise HTTPException(status_code=400, detail="Phone already exists")
    c = Customer(phone=phone, name=body.name, email=str(body.email) if body.email else None, notes=body.notes)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: str,
    body: CustomerUpdate,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    data = body.model_dump(exclude_unset=True)
    if "email" in data and data["email"] is not None:
        data["email"] = str(data["email"])
    for k, v in data.items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    return c


@router.get("/{customer_id}/orders", response_model=list[OrderOut])
def customer_orders(
    customer_id: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(Order)
        .filter(
            Order.customer_id == customer_id,
            Order.store_id == ctx.store_id,
            Order.status == OrderStatus.paid,
        )
        .order_by(Order.paid_at.desc())
        .limit(20)
        .all()
    )
    return orders


@router.get("/{customer_id}/timeline")
def customer_timeline(
    customer_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    """
    Unified CRM timeline: orders + point txns + audit logs related to customer/orders.
    """
    from pos.models.events import AuditLog
    from pos.models.loyalty import PointTransaction

    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Not found")

    events: list[dict] = []

    orders = (
        db.query(Order)
        .filter(Order.customer_id == customer_id, Order.store_id == ctx.store_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .all()
    )
    order_ids = [o.id for o in orders]
    for o in orders:
        kind = "order.paid" if o.status == OrderStatus.paid else f"order.{o.status.value}"
        events.append(
            {
                "at": (o.paid_at or o.created_at).isoformat() if (o.paid_at or o.created_at) else None,
                "kind": kind,
                "title": f"Đơn {o.status.value} · {o.total}",
                "ref_id": o.id,
                "meta": {"total": str(o.total), "status": o.status.value},
            }
        )

    pts = (
        db.query(PointTransaction)
        .filter(PointTransaction.customer_id == customer_id)
        .order_by(PointTransaction.created_at.desc())
        .limit(limit)
        .all()
    )
    for t in pts:
        events.append(
            {
                "at": t.created_at.isoformat() if t.created_at else None,
                "kind": f"points.{t.txn_type.value}",
                "title": f"Điểm {t.txn_type.value}: {t.points:+d}",
                "ref_id": t.id,
                "meta": {"points": t.points, "note": t.note, "order_id": t.order_id},
            }
        )

    if order_ids:
        audits = (
            db.query(AuditLog)
            .filter(AuditLog.entity == "order", AuditLog.entity_id.in_(order_ids))
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
        for a in audits:
            events.append(
                {
                    "at": a.created_at.isoformat() if a.created_at else None,
                    "kind": f"audit.{a.action}",
                    "title": a.action,
                    "ref_id": a.id,
                    "meta": {"detail": a.detail, "entity_id": a.entity_id},
                }
            )

    events.sort(key=lambda e: e.get("at") or "", reverse=True)
    return {
        "customer_id": customer_id,
        "count": len(events[:limit]),
        "events": events[:limit],
    }
