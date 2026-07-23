from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session, joinedload

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.catalog import Product
from pos.models.customers import Customer
from pos.models.orders import Order, OrderLine, OrderStatus, PaymentMethod
from pos.schemas import (
    OfflineSyncRequest,
    OrderCreate,
    OrderLineAdd,
    OrderLineUpdate,
    OrderOut,
    OrderUpdate,
    PayRequest,
    RefundRequest,
)
from pos.services.orders import atomic_pay, atomic_refund, recalculate_order, set_line_totals
from pos.utils import normalize_vn_phone

router = APIRouter(prefix="/orders")


def _load_order(db: Session, order_id: str, store_id: str) -> Order:
    order = (
        db.query(Order)
        .options(joinedload(Order.lines), joinedload(Order.payments))
        .filter(Order.id == order_id, Order.store_id == store_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/sync")
def sync_offline_orders(
    body: OfflineSyncRequest,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    """Replay offline POS orders: create + lines + atomic pay (idempotent by client_id)."""
    results = []
    for item in body.orders:
        try:
            existing = (
                db.query(Order)
                .filter(
                    Order.store_id == ctx.store_id,
                    Order.idempotency_key == f"offline:{item.client_id}",
                )
                .first()
            )
            if existing and existing.status == OrderStatus.paid:
                results.append(
                    {
                        "client_id": item.client_id,
                        "ok": True,
                        "order_id": existing.id,
                        "status": "already_synced",
                    }
                )
                continue

            customer_id = item.customer_id
            if not customer_id and item.customer_phone:
                phone = normalize_vn_phone(item.customer_phone)
                cust = db.query(Customer).filter(Customer.phone == phone).first()
                if not cust:
                    cust = Customer(phone=phone, name="")
                    db.add(cust)
                    db.flush()
                customer_id = cust.id

            order = Order(
                store_id=ctx.store_id,
                user_id=ctx.user.id,
                customer_id=customer_id,
                note=item.note,
                status=OrderStatus.draft,
                discount_percent=item.discount_percent or Decimal("0"),
            )
            db.add(order)
            db.flush()

            if not item.lines:
                raise ValueError("offline order has no lines")

            for line_in in item.lines:
                product = db.get(Product, line_in.product_id)
                if not product or product.deleted_at is not None:
                    raise ValueError(
                        f"conflict:product_missing:{line_in.product_id}"
                    )
                # server wins on price (offline conflict resolution P4-M1)
                price = product.price
                if line_in.unit_price is not None and Decimal(str(line_in.unit_price)) != product.price:
                    # keep server price; note conflict but continue
                    pass
                line = OrderLine(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name,
                    qty=line_in.qty,
                    unit_price=price,
                    line_discount=Decimal("0"),
                )
                set_line_totals(line)
                db.add(line)
                order.lines.append(line)

            recalculate_order(order)
            db.flush()
            atomic_pay(
                db,
                order,
                method=PaymentMethod(item.pay_method),
                amount=None,
                ref=f"offline:{item.client_id}",
                idempotency_key=f"offline:{item.client_id}",
            )
            results.append(
                {
                    "client_id": item.client_id,
                    "ok": True,
                    "order_id": order.id,
                    "status": "synced",
                    "resolution": "server_price_wins",
                }
            )
        except Exception as exc:
            db.rollback()
            err = str(exc)
            conflict = err.startswith("conflict:") or "Insufficient stock" in err or "product missing" in err
            results.append(
                {
                    "client_id": item.client_id,
                    "ok": False,
                    "error": err,
                    "status": "conflict" if conflict else "failed",
                    "resolution": "manual_resolve" if conflict else None,
                }
            )
    return {"ok": all(r.get("ok") for r in results) if results else True, "results": results}


@router.post("", response_model=OrderOut)
def create_order(
    body: OrderCreate,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    order = Order(
        store_id=ctx.store_id,
        user_id=ctx.user.id,
        customer_id=body.customer_id,
        note=body.note,
        status=OrderStatus.draft,
    )
    db.add(order)
    db.commit()
    return _load_order(db, order.id, ctx.store_id)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    return _load_order(db, order_id, ctx.store_id)


@router.patch("/{order_id}", response_model=OrderOut)
def update_order(
    order_id: str,
    body: OrderUpdate,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    order = _load_order(db, order_id, ctx.store_id)
    if order.status not in {OrderStatus.draft, OrderStatus.held}:
        raise HTTPException(status_code=400, detail="Order not editable")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(order, k, v)
    recalculate_order(order)
    db.commit()
    return _load_order(db, order.id, ctx.store_id)


@router.post("/{order_id}/lines", response_model=OrderOut)
def add_line(
    order_id: str,
    body: OrderLineAdd,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    order = _load_order(db, order_id, ctx.store_id)
    if order.status not in {OrderStatus.draft, OrderStatus.held}:
        raise HTTPException(status_code=400, detail="Order not editable")
    product = db.get(Product, body.product_id)
    if not product or product.deleted_at is not None or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = next((l for l in order.lines if l.product_id == product.id), None)
    if existing:
        existing.qty += body.qty
        set_line_totals(existing)
    else:
        line = OrderLine(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,
            qty=body.qty,
            unit_price=product.price,
            line_discount=Decimal("0"),
        )
        set_line_totals(line)
        db.add(line)
        order.lines.append(line)
    recalculate_order(order)
    db.commit()
    return _load_order(db, order.id, ctx.store_id)


@router.patch("/{order_id}/lines/{line_id}", response_model=OrderOut)
def update_line(
    order_id: str,
    line_id: str,
    body: OrderLineUpdate,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    order = _load_order(db, order_id, ctx.store_id)
    if order.status not in {OrderStatus.draft, OrderStatus.held}:
        raise HTTPException(status_code=400, detail="Order not editable")
    line = next((l for l in order.lines if l.id == line_id), None)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    if body.qty is not None:
        line.qty = body.qty
    if body.line_discount is not None:
        line.line_discount = body.line_discount
    set_line_totals(line)
    recalculate_order(order)
    db.commit()
    return _load_order(db, order.id, ctx.store_id)


@router.delete("/{order_id}/lines/{line_id}", response_model=OrderOut)
def delete_line(
    order_id: str,
    line_id: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    order = _load_order(db, order_id, ctx.store_id)
    if order.status not in {OrderStatus.draft, OrderStatus.held}:
        raise HTTPException(status_code=400, detail="Order not editable")
    line = next((l for l in order.lines if l.id == line_id), None)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    db.delete(line)
    db.flush()
    order = _load_order(db, order_id, ctx.store_id)
    recalculate_order(order)
    db.commit()
    return _load_order(db, order.id, ctx.store_id)


@router.post("/{order_id}/hold", response_model=OrderOut)
def hold_order(
    order_id: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    order = _load_order(db, order_id, ctx.store_id)
    if order.status != OrderStatus.draft:
        raise HTTPException(status_code=400, detail="Only draft can hold")
    order.status = OrderStatus.held
    db.commit()
    return _load_order(db, order.id, ctx.store_id)


@router.post("/{order_id}/resume", response_model=OrderOut)
def resume_order(
    order_id: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    order = _load_order(db, order_id, ctx.store_id)
    if order.status != OrderStatus.held:
        raise HTTPException(status_code=400, detail="Only held can resume")
    order.status = OrderStatus.draft
    db.commit()
    return _load_order(db, order.id, ctx.store_id)


@router.post("/{order_id}/pay", response_model=OrderOut)
def pay_order(
    order_id: str,
    body: PayRequest,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    order = _load_order(db, order_id, ctx.store_id)

    if idempotency_key:
        existing = (
            db.query(Order)
            .filter(Order.store_id == ctx.store_id, Order.idempotency_key == idempotency_key)
            .first()
        )
        if existing and existing.status == OrderStatus.paid:
            return _load_order(db, existing.id, ctx.store_id)

    if body.auto_create_customer_phone and not order.customer_id:
        phone = normalize_vn_phone(body.auto_create_customer_phone)
        cust = db.query(Customer).filter(Customer.phone == phone).first()
        if not cust:
            cust = Customer(phone=phone, name="")
            db.add(cust)
            db.flush()
        order.customer_id = cust.id

    try:
        # promo + loyalty redeem before pay
        from pos.services.loyalty import redeem_points
        from pos.services.promo import apply_promo_to_order

        if body.promo_code:
            apply_promo_to_order(db, order, code=body.promo_code)
        else:
            apply_promo_to_order(db, order, code=None)

        if body.redeem_points and order.customer_id:
            disc = redeem_points(db, order.customer_id, body.redeem_points, order_id=order.id)
            order.discount = (order.discount + disc).quantize(Decimal("0.01"))
            order.total = max(order.subtotal - order.discount + order.tax, Decimal("0")).quantize(
                Decimal("0.01")
            )
            db.add(order)
            db.flush()

        atomic_pay(
            db,
            order,
            method=PaymentMethod(body.method),
            amount=body.amount,
            ref=body.ref,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _load_order(db, order.id, ctx.store_id)


@router.post("/{order_id}/void", response_model=OrderOut)
def void_order(
    order_id: str,
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    order = _load_order(db, order_id, ctx.store_id)
    if order.status == OrderStatus.paid:
        raise HTTPException(status_code=400, detail="Use POST /orders/{id}/refund for paid orders")
    if order.status == OrderStatus.refunded:
        raise HTTPException(status_code=400, detail="Order already refunded")
    order.status = OrderStatus.void
    db.commit()
    return _load_order(db, order.id, ctx.store_id)


@router.post("/{order_id}/refund", response_model=OrderOut)
def refund_order(
    order_id: str,
    body: RefundRequest = RefundRequest(),
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    """Full refund: restore stock + reverse loyalty points + status=refunded."""
    order = _load_order(db, order_id, ctx.store_id)
    try:
        atomic_refund(db, order, reason=body.reason, actor_id=ctx.user.id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _load_order(db, order.id, ctx.store_id)


@router.get("/{order_id}/receipt")
def receipt(
    order_id: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    order = _load_order(db, order_id, ctx.store_id)
    lines = []
    lines.append("=" * 32)
    lines.append("        HOA DON BAN HANG")
    lines.append(f"Order: {order.id[:8]}")
    lines.append(f"Status: {order.status.value}")
    lines.append("-" * 32)
    for line in order.lines:
        lines.append(f"{line.product_name}")
        lines.append(f"  {line.qty} x {line.unit_price} = {line.line_total}")
    lines.append("-" * 32)
    lines.append(f"Subtotal: {order.subtotal}")
    lines.append(f"Discount: {order.discount}")
    lines.append(f"TOTAL:    {order.total}")
    if order.payments:
        for p in order.payments:
            lines.append(f"Pay {p.method.value}: {p.amount}")
    lines.append("=" * 32)
    lines.append("Cam on quy khach!")
    return {"order_id": order.id, "text": "\n".join(lines)}
