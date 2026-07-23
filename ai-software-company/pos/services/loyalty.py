from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from pos.models.loyalty import CustomerPoints, LoyaltyProgram, PointTransaction, PointTxnType
from pos.models.orders import Order

# Default earn-point TTL (days). Override per call on expire job.
DEFAULT_POINTS_TTL_DAYS = 365


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


def reverse_order_points(db: Session, order: Order) -> int:
    """
    Reverse earn/redeem transactions for a refunded order.
    Returns net points adjusted on balance (can be negative).
    """
    if not order.customer_id:
        return 0
    txns = (
        db.query(PointTransaction)
        .filter(
            PointTransaction.order_id == order.id,
            PointTransaction.txn_type.in_([PointTxnType.earn, PointTxnType.redeem]),
        )
        .all()
    )
    if not txns:
        return 0
    bal = get_or_create_balance(db, order.customer_id)
    net = 0
    for t in txns:
        # earn was +, redeem was −; reverse both
        reverse = -t.points
        bal.balance += reverse
        if t.txn_type == PointTxnType.earn and t.points > 0:
            bal.lifetime_earned = max(0, bal.lifetime_earned - t.points)
        net += reverse
        db.add(
            PointTransaction(
                customer_id=order.customer_id,
                order_id=order.id,
                txn_type=PointTxnType.adjust,
                points=reverse,
                note=f"Reverse {t.txn_type.value} on refund {order.id[:8]}",
            )
        )
    if bal.balance < 0:
        bal.balance = 0
    return net


def expire_stale_points(db: Session, *, ttl_days: int = DEFAULT_POINTS_TTL_DAYS) -> dict:
    """
    Expire un-consumed earn points older than ttl_days (FIFO-ish per customer).
    For each customer: sum earn older than cutoff, subtract already redeemed/expired/adjusted,
    expire remaining positive balance from old earns (capped by current balance).
    """
    cutoff = datetime.now(UTC) - timedelta(days=ttl_days)
    customers = db.query(CustomerPoints).all()
    expired_customers = 0
    expired_points = 0

    for bal in customers:
        if bal.balance <= 0:
            continue
        old_earns = (
            db.query(PointTransaction)
            .filter(
                PointTransaction.customer_id == bal.customer_id,
                PointTransaction.txn_type == PointTxnType.earn,
                PointTransaction.created_at < cutoff,
            )
            .all()
        )
        if not old_earns:
            continue
        old_earn_sum = sum(t.points for t in old_earns if t.points > 0)
        # how much already clawed back via redeem/expire/adjust after those earns
        later = (
            db.query(PointTransaction)
            .filter(
                PointTransaction.customer_id == bal.customer_id,
                PointTransaction.txn_type.in_(
                    [PointTxnType.redeem, PointTxnType.expire, PointTxnType.adjust]
                ),
            )
            .all()
        )
        # negative points reduce available old pool
        clawed = sum(-t.points for t in later if t.points < 0)
        remaining_old = max(0, old_earn_sum - clawed)
        to_expire = min(bal.balance, remaining_old)
        if to_expire <= 0:
            continue
        bal.balance -= to_expire
        db.add(
            PointTransaction(
                customer_id=bal.customer_id,
                order_id=None,
                txn_type=PointTxnType.expire,
                points=-to_expire,
                note=f"Auto expire points older than {ttl_days}d",
            )
        )
        expired_customers += 1
        expired_points += to_expire

    db.commit()
    return {
        "ttl_days": ttl_days,
        "customers_affected": expired_customers,
        "points_expired": expired_points,
        "cutoff": cutoff.isoformat(),
    }
