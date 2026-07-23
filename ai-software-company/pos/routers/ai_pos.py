from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.services.recommend import recommend_products

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/recommend")
def recommend(
    product_ids: str | None = Query(default=None, description="Comma-separated product ids in cart"),
    customer_id: str | None = None,
    limit: int = 5,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    ids = [x for x in (product_ids or "").split(",") if x.strip()]
    items = recommend_products(
        db,
        store_id=ctx.store_id,
        product_ids=ids,
        customer_id=customer_id,
        limit=limit,
    )
    coach = None
    if items:
        top = items[0]
        coach = f"Khách thường mua kèm: {top['name']} — gợi ý upsell."
    return {"items": items, "next_best_action": coach}


@router.get("/coach")
def coach(
    product_ids: str | None = None,
    customer_id: str | None = None,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    rec = recommend(
        product_ids=product_ids,
        customer_id=customer_id,
        limit=3,
        ctx=ctx,
        db=db,
    )
    return {
        "message": rec.get("next_best_action") or "Chưa đủ dữ liệu — bán theo catalog.",
        "recommendations": rec["items"],
    }
