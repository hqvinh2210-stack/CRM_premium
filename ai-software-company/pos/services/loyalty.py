from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from pos.models.loyalty import CustomerPoints, LoyaltyProgram, PointTransaction, PointTxnType
from pos.models.orders import Order


def get_active_program(db: Session) -> LoyaltyProgram | None:
    return db.query(LoyaltyProgram).filter(LoyaltyProgram.is_active.is_(True)).first()


def get_or_create_balance(db: Session, customer_id: str) -> CustomerPoints:
    row = db.query(CustomerPoints).filter(CustomerPoints.customer_id == customer_id).first()
    if not row:
        row = CustomerPoints(customer_id=customer_id, balance=0, lifetime_earned=0)
        db.add(row)
        db.flush()
    return row


def earn_on_order(db: Session, order: Order) -> int:
    if not order.customer_id:
        return 0
    program = get_active_program(db)
    if not program:
        return 0
    points = int((order.total * program.earn_rate).quantize(Decimal("1")))
    if points <= 0:
        return 0
    bal = get_or_create_balance(db, order.customer_id)
    bal.balance += points
    bal.lifetime_earned += points
    db.add(
        PointTransaction(
            customer_id=order.customer_id,
            order_id=order.id,
            txn_type=PointTxnType.earn,
            points=points,
            note=f"Earn on order {order.id[:8]}",
        )
    )
    return points


def redeem_points(db: Session, customer_id: str, points: int, order_id: str | None = None) -> Decimal:
    """Redeem points → money discount. Returns VND discount amount."""
    if points <= 0:
        return Decimal("0")
    program = get_active_program(db)
    if not program:
        raise ValueError("No active loyalty program")
    bal = get_or_create_balance(db, customer_id)
    if bal.balance < points:
        raise ValueError(f"Insufficient points: have {bal.balance}, need {points}")
    bal.balance -= points
    db.add(
        PointTransaction(
            customer_id=customer_id,
            order_id=order_id,
            txn_type=PointTxnType.redeem,
            points=-points,
            note="Redeem at checkout",
        )
    )
    return (Decimal(points) * program.redeem_value).quantize(Decimal("0.01"))
