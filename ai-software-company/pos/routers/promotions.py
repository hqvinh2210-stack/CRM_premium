from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.promo import PromoType, Promotion
from pos.routers.orders import _load_order
from pos.services.promo import active_promotions, apply_promo_to_order

router = APIRouter(prefix="/promotions", tags=["promotions"])


class PromoCreate(BaseModel):
    name: str
    promo_type: str = "percent"
    value: Decimal = Field(ge=0)
    code: str | None = None
    min_subtotal: Decimal = Decimal("0")
    buy_qty: int = 0
    free_qty: int = 0


@router.get("")
def list_promos(
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    rows = active_promotions(db)
    return {
        "promotions": [
            {
                "id": p.id,
                "name": p.name,
                "code": p.code,
                "promo_type": p.promo_type.value,
                "value": str(p.value),
                "min_subtotal": str(p.min_subtotal),
            }
            for p in rows
        ]
    }


@router.post("")
def create_promo(
    body: PromoCreate,
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    try:
        ptype = PromoType(body.promo_type)
    except ValueError as exc:
        raise HTTPException(400, "Invalid promo_type") from exc
    p = Promotion(
        name=body.name,
        promo_type=ptype,
        value=body.value,
        code=body.code,
        min_subtotal=body.min_subtotal,
        buy_qty=body.buy_qty,
        free_qty=body.free_qty,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "name": p.name, "code": p.code}


class ApplyPromo(BaseModel):
    code: str | None = None


@router.post("/orders/{order_id}/apply")
def apply_to_order(
    order_id: str,
    body: ApplyPromo,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    order = _load_order(db, order_id, ctx.store_id)
    result = apply_promo_to_order(db, order, code=body.code)
    db.commit()
    return result
