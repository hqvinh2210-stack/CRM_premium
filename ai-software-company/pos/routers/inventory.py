from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.catalog import Product, StockLevel
from pos.models.inventory_ext import StockTransfer, Stocktake, TransferStatus
from pos.services.events import audit, publish_event
from pos.services.orders import get_stock

router = APIRouter(prefix="/inventory", tags=["inventory"])


class TransferIn(BaseModel):
    from_store_id: str
    to_store_id: str
    product_id: str
    qty: int = Field(ge=1)
    note: str | None = None


@router.post("/transfers")
def create_transfer(
    body: TransferIn,
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    if body.from_store_id == body.to_store_id:
        raise HTTPException(400, "from/to store must differ")
    product = db.get(Product, body.product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    src = (
        db.query(StockLevel)
        .filter(StockLevel.store_id == body.from_store_id, StockLevel.product_id == body.product_id)
        .with_for_update(of=StockLevel)
        .first()
    )
    if not src or src.qty < body.qty:
        raise HTTPException(400, "Insufficient stock at source")

    dst = (
        db.query(StockLevel)
        .filter(StockLevel.store_id == body.to_store_id, StockLevel.product_id == body.product_id)
        .with_for_update(of=StockLevel)
        .first()
    )
    if not dst:
        dst = StockLevel(store_id=body.to_store_id, product_id=body.product_id, qty=0, version=0)
        db.add(dst)
        db.flush()

    src.qty -= body.qty
    src.version += 1
    dst.qty += body.qty
    dst.version += 1

    tr = StockTransfer(
        from_store_id=body.from_store_id,
        to_store_id=body.to_store_id,
        product_id=body.product_id,
        qty=body.qty,
        status=TransferStatus.completed,
        note=body.note,
        created_by=ctx.user.id,
        completed_at=datetime.now(UTC),
    )
    db.add(tr)
    publish_event(
        db,
        "stock.updated",
        {
            "transfer_id": tr.id,
            "from": body.from_store_id,
            "to": body.to_store_id,
            "product_id": body.product_id,
            "qty": body.qty,
        },
    )
    audit(db, actor_id=ctx.user.id, action="stock.transfer", entity="stock_transfer", entity_id=tr.id)
    db.commit()
    db.refresh(tr)
    return {
        "id": tr.id,
        "status": tr.status.value,
        "from_store_id": tr.from_store_id,
        "to_store_id": tr.to_store_id,
        "product_id": tr.product_id,
        "qty": tr.qty,
    }


class StocktakeIn(BaseModel):
    product_id: str
    counted_qty: int = Field(ge=0)
    note: str | None = None
    apply_adjustment: bool = True


@router.post("/stocktake")
def stocktake(
    body: StocktakeIn,
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    stock = get_stock(db, ctx.store_id, body.product_id)
    system_qty = stock.qty if stock else 0
    variance = body.counted_qty - system_qty
    st = Stocktake(
        store_id=ctx.store_id,
        product_id=body.product_id,
        system_qty=system_qty,
        counted_qty=body.counted_qty,
        variance=variance,
        note=body.note,
        created_by=ctx.user.id,
    )
    db.add(st)
    if body.apply_adjustment:
        if not stock:
            stock = StockLevel(store_id=ctx.store_id, product_id=body.product_id, qty=0, version=0)
            db.add(stock)
            db.flush()
        stock.qty = body.counted_qty
        stock.version += 1
        publish_event(
            db,
            "stock.updated",
            {"store_id": ctx.store_id, "product_id": body.product_id, "qty": body.counted_qty, "via": "stocktake"},
        )
    db.commit()
    return {
        "id": st.id,
        "system_qty": system_qty,
        "counted_qty": body.counted_qty,
        "variance": variance,
        "applied": body.apply_adjustment,
    }


@router.get("/low-stock")
def low_stock(
    threshold: int = 10,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(StockLevel, Product)
        .join(Product, Product.id == StockLevel.product_id)
        .filter(
            StockLevel.store_id == ctx.store_id,
            StockLevel.qty <= threshold,
            Product.track_inventory.is_(True),
            Product.deleted_at.is_(None),
        )
        .all()
    )
    return {
        "threshold": threshold,
        "items": [
            {
                "product_id": p.id,
                "sku": p.sku,
                "name": p.name,
                "qty": s.qty,
            }
            for s, p in rows
        ],
    }
