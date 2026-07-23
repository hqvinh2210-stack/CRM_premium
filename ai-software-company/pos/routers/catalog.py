from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.catalog import Product, StockLevel
from pos.schemas import ProductCreate, ProductOut, ProductUpdate, StockAdjustRequest, StockOut

router = APIRouter()


def _product_out(db: Session, product: Product, store_id: str) -> ProductOut:
    stock = (
        db.query(StockLevel)
        .filter(StockLevel.store_id == store_id, StockLevel.product_id == product.id)
        .first()
    )
    data = ProductOut.model_validate(product)
    data.stock_qty = stock.qty if stock else 0
    return data


@router.get("/products", response_model=list[ProductOut])
def list_products(
    q: str | None = None,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    query = db.query(Product).filter(Product.deleted_at.is_(None), Product.is_active.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Product.name.ilike(like), Product.sku.ilike(like), Product.barcode.ilike(like))
        )
    products = query.order_by(Product.name).limit(100).all()
    return [_product_out(db, p, ctx.store_id) for p in products]


@router.get("/products/search", response_model=list[ProductOut])
def search_products(
    q: str = Query(..., min_length=1),
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    return list_products(q=q, ctx=ctx, db=db)


@router.get("/products/barcode/{code}", response_model=ProductOut)
def get_by_barcode(
    code: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    p = (
        db.query(Product)
        .filter(Product.barcode == code, Product.deleted_at.is_(None), Product.is_active.is_(True))
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return _product_out(db, p, ctx.store_id)


@router.post("/products", response_model=ProductOut)
def create_product(
    body: ProductCreate,
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    if db.query(Product).filter(Product.sku == body.sku).first():
        raise HTTPException(status_code=400, detail="SKU exists")
    if body.barcode and db.query(Product).filter(Product.barcode == body.barcode).first():
        raise HTTPException(status_code=400, detail="Barcode exists")
    p = Product(
        sku=body.sku,
        name=body.name,
        price=body.price,
        cost=body.cost,
        barcode=body.barcode,
        category_id=body.category_id,
        track_inventory=body.track_inventory,
        description=body.description,
    )
    db.add(p)
    db.flush()
    db.add(StockLevel(store_id=ctx.store_id, product_id=p.id, qty=body.initial_qty))
    db.commit()
    db.refresh(p)
    return _product_out(db, p, ctx.store_id)


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: str,
    body: ProductUpdate,
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    p = db.get(Product, product_id)
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return _product_out(db, p, ctx.store_id)


@router.delete("/products/{product_id}")
def soft_delete_product(
    product_id: str,
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    p.deleted_at = datetime.now(UTC)
    p.is_active = False
    db.commit()
    return {"ok": True}


@router.post("/stock/adjust", response_model=StockOut)
def adjust_stock(
    body: StockAdjustRequest,
    ctx: AuthContext = Depends(require_any("manager", "admin")),
    db: Session = Depends(get_db),
):
    stock = (
        db.query(StockLevel)
        .filter(StockLevel.store_id == ctx.store_id, StockLevel.product_id == body.product_id)
        .first()
    )
    if not stock:
        stock = StockLevel(store_id=ctx.store_id, product_id=body.product_id, qty=0, version=0)
        db.add(stock)
        db.flush()
    if body.expected_version is not None and stock.version != body.expected_version:
        raise HTTPException(status_code=409, detail="Stock version conflict")
    new_qty = stock.qty + body.delta
    if new_qty < 0:
        raise HTTPException(status_code=400, detail="Stock would be negative")
    stock.qty = new_qty
    stock.version += 1
    db.commit()
    db.refresh(stock)
    return StockOut(
        product_id=stock.product_id,
        store_id=stock.store_id,
        qty=stock.qty,
        version=stock.version,
    )
