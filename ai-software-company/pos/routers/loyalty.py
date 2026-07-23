from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.loyalty import LoyaltyProgram, Reward
from pos.services.loyalty import get_active_program, get_or_create_balance

router = APIRouter(prefix="/loyalty", tags=["loyalty"])


class ProgramOut(BaseModel):
    id: str
    name: str
    earn_rate: str
    redeem_value: str
    is_active: bool


@router.get("/program")
def get_program(
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    p = get_active_program(db)
    if not p:
        return {"program": None}
    return {
        "program": {
            "id": p.id,
            "name": p.name,
            "earn_rate": str(p.earn_rate),
            "redeem_value": str(p.redeem_value),
            "is_active": p.is_active,
        }
    }


@router.get("/points/{customer_id}")
def customer_points(
    customer_id: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    bal = get_or_create_balance(db, customer_id)
    db.commit()
    program = get_active_program(db)
    vnd = int(bal.balance * float(program.redeem_value)) if program else 0
    return {
        "customer_id": customer_id,
        "balance": bal.balance,
        "lifetime_earned": bal.lifetime_earned,
        "redeemable_vnd": vnd,
    }


@router.get("/rewards")
def list_rewards(
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    rows = db.query(Reward).filter(Reward.is_active.is_(True)).all()
    return {
        "rewards": [
            {"id": r.id, "name": r.name, "points_cost": r.points_cost, "description": r.description}
            for r in rows
        ]
    }


class PreviewRedeem(BaseModel):
    customer_id: str
    points: int = Field(ge=1)


@router.post("/preview-redeem")
def preview_redeem(
    body: PreviewRedeem,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    program = get_active_program(db)
    if not program:
        raise HTTPException(400, "No program")
    bal = get_or_create_balance(db, body.customer_id)
    if bal.balance < body.points:
        raise HTTPException(400, f"Insufficient points ({bal.balance})")
    return {
        "points": body.points,
        "discount_vnd": str(body.points * program.redeem_value),
        "balance_after": bal.balance - body.points,
    }


class ExpireIn(BaseModel):
    ttl_days: int = Field(default=365, ge=1, le=3650)


@router.post("/expire")
def expire_points(
    body: ExpireIn | None = None,
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    """Expire stale earn points older than ttl_days (loyalty expiry job)."""
    from pos.services.loyalty import expire_stale_points

    ttl = body.ttl_days if body else 365
    return expire_stale_points(db, ttl_days=ttl)

