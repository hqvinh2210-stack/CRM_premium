from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from pos.models.catalog import Product
from pos.models.orders import Order, OrderLine, OrderStatus


def recommend_products(
    db: Session,
    *,
    store_id: str,
    product_ids: list[str] | None = None,
    customer_id: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """
    Simple co-purchase + popularity recommender (no external ML required).
    """
    product_ids = product_ids or []
    # co-purchase: products that appear with given products on paid orders
    scores: Counter[str] = Counter()

    if product_ids:
        # orders containing any of product_ids
        order_ids = (
            db.query(OrderLine.order_id)
            .join(Order, Order.id == OrderLine.order_id)
            .filter(
                Order.store_id == store_id,
                Order.status == OrderStatus.paid,
                OrderLine.product_id.in_(product_ids),
            )
            .distinct()
            .all()
        )
        oids = [o[0] for o in order_ids]
        if oids:
            others = (
                db.query(OrderLine.product_id)
                .filter(OrderLine.order_id.in_(oids), ~OrderLine.product_id.in_(product_ids))
                .all()
            )
            scores.update(x[0] for x in others)

    if customer_id:
        past = (
            db.query(OrderLine.product_id)
            .join(Order, Order.id == OrderLine.order_id)
            .filter(
                Order.customer_id == customer_id,
                Order.store_id == store_id,
                Order.status == OrderStatus.paid,
            )
            .all()
        )
        for pid, in past:
            if pid not in product_ids:
                scores[pid] += 2

    # popularity fallback
    if len(scores) < limit:
        pop = (
            db.query(OrderLine.product_id)
            .join(Order, Order.id == OrderLine.order_id)
            .filter(Order.store_id == store_id, Order.status == OrderStatus.paid)
            .all()
        )
        scores.update(x[0] for x in pop)

    out = []
    for pid, score in scores.most_common(limit + len(product_ids)):
        if pid in product_ids:
            continue
        p = db.get(Product, pid)
        if not p or p.deleted_at is not None or not p.is_active:
            continue
        out.append(
            {
                "product_id": p.id,
                "sku": p.sku,
                "name": p.name,
                "price": str(p.price),
                "score": score,
                "reason": "co-purchase / history",
            }
        )
        if len(out) >= limit:
            break

    # if still empty, random active products
    if not out:
        for p in db.query(Product).filter(Product.is_active.is_(True), Product.deleted_at.is_(None)).limit(limit):
            if p.id in product_ids:
                continue
            out.append(
                {
                    "product_id": p.id,
                    "sku": p.sku,
                    "name": p.name,
                    "price": str(p.price),
                    "score": 0,
                    "reason": "popular_fallback",
                }
            )
    return out
