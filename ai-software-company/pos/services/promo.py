from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from pos.models.orders import Order
from pos.models.promo import PromoType, Promotion


def active_promotions(db: Session) -> list[Promotion]:
    now = datetime.now(UTC)
    rows = db.query(Promotion).filter(Promotion.is_active.is_(True)).all()
    out = []
    for p in rows:
        if p.starts_at and p.starts_at > now:
            continue
        if p.ends_at and p.ends_at < now:
            continue
        out.append(p)
    return out


def apply_promo_to_order(db: Session, order: Order, code: str | None = None) -> dict:
    """
    Apply best matching promotion (or coupon code).
    Mutates order.discount / total after subtotal calc.
    """
    from pos.services.orders import recalculate_order

    # base from lines + percent field first
    recalculate_order(order)
    subtotal = order.subtotal
    extra = Decimal("0")
    applied = None

    promos = active_promotions(db)
    if code:
        match = next((p for p in promos if p.code and p.code.upper() == code.upper()), None)
        candidates = [match] if match else []
    else:
        candidates = [p for p in promos if p.promo_type != PromoType.coupon]

    best_discount = Decimal("0")
    for p in candidates:
        if not p:
            continue
        if subtotal < (p.min_subtotal or 0):
            continue
        d = Decimal("0")
        if p.promo_type in {PromoType.percent, PromoType.coupon} and p.promo_type != PromoType.fixed:
            # coupon can be percent value
            if p.promo_type == PromoType.coupon:
                d = (subtotal * p.value / Decimal("100")).quantize(Decimal("0.01"))
            else:
                d = (subtotal * p.value / Decimal("100")).quantize(Decimal("0.01"))
        if p.promo_type == PromoType.percent:
            d = (subtotal * p.value / Decimal("100")).quantize(Decimal("0.01"))
        elif p.promo_type == PromoType.fixed:
            d = min(p.value, subtotal)
        elif p.promo_type == PromoType.coupon:
            d = (subtotal * p.value / Decimal("100")).quantize(Decimal("0.01"))
        elif p.promo_type == PromoType.bxgy and p.buy_qty > 0:
            total_qty = sum(l.qty for l in order.lines)
            free_units = (total_qty // (p.buy_qty + p.free_qty)) * p.free_qty if p.free_qty else 0
            if free_units and order.lines:
                cheapest = min(order.lines, key=lambda l: l.unit_price)
                d = (cheapest.unit_price * free_units).quantize(Decimal("0.01"))
        if d > best_discount:
            best_discount = d
            applied = p

    # stack: cart percent discount already in order.discount; add promo as extra on subtotal
    # redefine: total discount = max(order.discount from %, best_discount) simple: add promo on top of %
    order.discount = (order.discount + best_discount).quantize(Decimal("0.01"))
    order.total = max(subtotal - order.discount + order.tax, Decimal("0")).quantize(Decimal("0.01"))
    return {
        "promo_id": applied.id if applied else None,
        "promo_name": applied.name if applied else None,
        "promo_discount": str(best_discount),
        "total": str(order.total),
    }
