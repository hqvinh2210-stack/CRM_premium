from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.orders import Order, OrderLine, OrderStatus, Payment

router = APIRouter(prefix="/reports")


@router.get("/rfm")
def rfm_segments(
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    """Simple RFM segmentation for customers with paid orders in this store."""
    from datetime import datetime, timedelta
    from pos.models.customers import Customer

    since = datetime.utcnow() - timedelta(days=365)
    customers = db.query(Customer).all()
    segments = []
    for c in customers:
        orders = (
            db.query(Order)
            .filter(
                Order.customer_id == c.id,
                Order.store_id == ctx.store_id,
                Order.status == OrderStatus.paid,
                Order.paid_at.isnot(None),
            )
            .all()
        )
        if not orders:
            continue
        last = max(o.paid_at for o in orders if o.paid_at)
        recency_days = (datetime.utcnow() - last.replace(tzinfo=None)).days if last else 999
        frequency = len(orders)
        from decimal import Decimal as Dec

        monetary = sum((o.total for o in orders), Dec("0"))
        # crude scores 1-3
        r = 3 if recency_days <= 30 else 2 if recency_days <= 90 else 1
        f = 3 if frequency >= 5 else 2 if frequency >= 2 else 1
        m = 3 if monetary >= 500000 else 2 if monetary >= 100000 else 1
        label = "Champions" if r + f + m >= 8 else "Loyal" if r + f + m >= 6 else "At Risk" if r == 1 else "Potential"
        segments.append(
            {
                "customer_id": c.id,
                "name": c.name,
                "phone": c.phone,
                "recency_days": recency_days,
                "frequency": frequency,
                "monetary": str(monetary),
                "rfm": f"{r}{f}{m}",
                "segment": label,
            }
        )
    return {"segments": segments, "count": len(segments)}


@router.get("/daily-sales")
def daily_sales(
    report_date: date | None = Query(default=None, alias="date"),
    ctx: AuthContext = Depends(require_any("manager", "admin", "cashier")),
    db: Session = Depends(get_db),
):
    day = report_date or date.today()
    start = datetime.combine(day, time.min)
    end = datetime.combine(day, time.max)

    orders = (
        db.query(Order)
        .filter(
            Order.store_id == ctx.store_id,
            Order.status == OrderStatus.paid,
            Order.paid_at >= start,
            Order.paid_at <= end,
        )
        .all()
    )
    gross = sum((o.subtotal for o in orders), Decimal("0"))
    discount = sum((o.discount for o in orders), Decimal("0"))
    net = sum((o.total for o in orders), Decimal("0"))

    by_method: dict[str, Decimal] = {}
    for o in orders:
        for p in o.payments:
            key = p.method.value
            by_method[key] = by_method.get(key, Decimal("0")) + p.amount

    # top products
    top_rows = (
        db.query(
            OrderLine.product_name,
            func.sum(OrderLine.qty).label("qty"),
            func.sum(OrderLine.line_total).label("revenue"),
        )
        .join(Order, Order.id == OrderLine.order_id)
        .filter(
            Order.store_id == ctx.store_id,
            Order.status == OrderStatus.paid,
            Order.paid_at >= start,
            Order.paid_at <= end,
        )
        .group_by(OrderLine.product_name)
        .order_by(func.sum(OrderLine.line_total).desc())
        .limit(10)
        .all()
    )
    top_products = [
        {"name": r.product_name, "qty": int(r.qty or 0), "revenue": str(r.revenue or 0)}
        for r in top_rows
    ]

    return {
        "date": day.isoformat(),
        "store_id": ctx.store_id,
        "order_count": len(orders),
        "gross": str(gross),
        "discount": str(discount),
        "net": str(net),
        "by_payment_method": {k: str(v) for k, v in by_method.items()},
        "top_products": top_products,
    }
