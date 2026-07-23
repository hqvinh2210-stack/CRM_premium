from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from pos.models.catalog import Product, StockLevel
from pos.models.orders import Order, OrderLine, OrderStatus, Payment, PaymentMethod


def recalculate_order(order: Order) -> None:
    subtotal = sum((line.line_total for line in order.lines), Decimal("0"))
    pct = order.discount_percent or Decimal("0")
    discount = (subtotal * pct / Decimal("100")).quantize(Decimal("0.01"))
    tax = Decimal("0")
    order.subtotal = subtotal
    order.discount = discount
    order.tax = tax
    order.total = (subtotal - discount + tax).quantize(Decimal("0.01"))
    if order.total < 0:
        order.total = Decimal("0")


def set_line_totals(line: OrderLine) -> None:
    raw = (line.unit_price * line.qty) - (line.line_discount or Decimal("0"))
    line.line_total = max(raw, Decimal("0")).quantize(Decimal("0.01"))


def get_stock(db: Session, store_id: str, product_id: str) -> StockLevel | None:
    return (
        db.query(StockLevel)
        .filter(StockLevel.store_id == store_id, StockLevel.product_id == product_id)
        .with_for_update(of=StockLevel)
        .first()
    )


def atomic_pay(
    db: Session,
    order: Order,
    *,
    method: PaymentMethod,
    amount: Decimal | None,
    ref: str | None,
    idempotency_key: str | None,
) -> Order:
    if order.status == OrderStatus.paid:
        return order
    if order.status not in {OrderStatus.draft, OrderStatus.held}:
        raise ValueError(f"Cannot pay order in status {order.status}")
    if not order.lines:
        raise ValueError("Order has no lines")

    recalculate_order(order)
    pay_amount = amount if amount is not None else order.total

    # stock checks + decrement
    for line in order.lines:
        product = db.get(Product, line.product_id)
        if not product or product.deleted_at is not None:
            raise ValueError(f"Product missing: {line.product_id}")
        if not product.track_inventory:
            continue
        stock = get_stock(db, order.store_id, product.id)
        if stock is None:
            raise ValueError(f"No stock row for product {product.sku}")
        if stock.qty < line.qty:
            raise ValueError(f"Insufficient stock for {product.sku}: have {stock.qty}, need {line.qty}")
        stock.qty -= line.qty
        stock.version += 1

    payment = Payment(
        order_id=order.id,
        method=method,
        amount=pay_amount,
        ref=ref,
        idempotency_key=idempotency_key,
    )
    order.status = OrderStatus.paid
    order.paid_at = datetime.now(UTC)
    if idempotency_key:
        order.idempotency_key = idempotency_key
    db.add(payment)
    db.add(order)

    # Phase 2–3 side effects
    try:
        from pos.services.events import audit, publish_event
        from pos.services.loyalty import earn_on_order

        earned = earn_on_order(db, order)
        publish_event(
            db,
            "order.created",
            {
                "order_id": order.id,
                "store_id": order.store_id,
                "customer_id": order.customer_id,
                "total": str(order.total),
                "points_earned": earned,
            },
        )
        publish_event(
            db,
            "stock.updated",
            {
                "store_id": order.store_id,
                "order_id": order.id,
                "lines": [{"product_id": l.product_id, "qty": l.qty} for l in order.lines],
            },
        )
        audit(
            db,
            actor_id=order.user_id,
            action="order.paid",
            entity="order",
            entity_id=order.id,
            detail=f"total={order.total} points={earned}",
        )
    except Exception:
        # never block payment on side-effects
        pass

    db.commit()
    db.refresh(order)
    return order

