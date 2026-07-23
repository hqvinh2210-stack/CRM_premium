from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.customers import Customer
from pos.models.orders import Order, OrderStatus
from pos.schemas import CustomerCreate, CustomerOut, CustomerUpdate, OrderOut
from pos.utils import normalize_vn_phone

router = APIRouter(prefix="/customers")


@router.get("/search", response_model=list[CustomerOut])
def search_customers(
    q: str = Query(..., min_length=1),
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    phone = normalize_vn_phone(q)
    like = f"%{q}%"
    rows = (
        db.query(Customer)
        .filter(or_(Customer.phone.contains(phone), Customer.name.ilike(like)))
        .limit(20)
        .all()
    )
    return rows


@router.post("", response_model=CustomerOut)
def create_customer(
    body: CustomerCreate,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    phone = normalize_vn_phone(body.phone)
    if db.query(Customer).filter(Customer.phone == phone).first():
        raise HTTPException(status_code=400, detail="Phone already exists")
    c = Customer(phone=phone, name=body.name, email=str(body.email) if body.email else None, notes=body.notes)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: str,
    body: CustomerUpdate,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    data = body.model_dump(exclude_unset=True)
    if "email" in data and data["email"] is not None:
        data["email"] = str(data["email"])
    for k, v in data.items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    return c


@router.get("/{customer_id}/orders", response_model=list[OrderOut])
def customer_orders(
    customer_id: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(Order)
        .filter(
            Order.customer_id == customer_id,
            Order.store_id == ctx.store_id,
            Order.status == OrderStatus.paid,
        )
        .order_by(Order.paid_at.desc())
        .limit(20)
        .all()
    )
    return orders
