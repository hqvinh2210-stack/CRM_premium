from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Auth ----
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    store_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    store_id: str | None = None
    role: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(ORMModel):
    id: str
    email: EmailStr
    phone: str | None
    full_name: str
    is_active: bool


class StoreOut(ORMModel):
    id: str
    code: str
    name: str
    address: str | None
    timezone: str
    is_active: bool


class StoreCreate(BaseModel):
    code: str
    name: str
    address: str | None = None
    timezone: str = "Asia/Ho_Chi_Minh"


class MeResponse(BaseModel):
    user: UserOut
    stores: list[dict]


# ---- Catalog ----
class ProductCreate(BaseModel):
    sku: str
    name: str
    price: Decimal = Field(ge=0)
    cost: Decimal = Field(default=Decimal("0"), ge=0)
    barcode: str | None = None
    category_id: str | None = None
    track_inventory: bool = True
    description: str | None = None
    initial_qty: int = 0


class ProductUpdate(BaseModel):
    name: str | None = None
    price: Decimal | None = None
    cost: Decimal | None = None
    barcode: str | None = None
    category_id: str | None = None
    track_inventory: bool | None = None
    description: str | None = None
    is_active: bool | None = None


class ProductOut(ORMModel):
    id: str
    sku: str
    name: str
    price: Decimal
    cost: Decimal
    barcode: str | None
    category_id: str | None
    track_inventory: bool
    is_active: bool
    stock_qty: int | None = None


class StockAdjustRequest(BaseModel):
    product_id: str
    delta: int
    reason: str = "manual"
    expected_version: int | None = None


class StockOut(BaseModel):
    product_id: str
    store_id: str
    qty: int
    version: int


# ---- Customers ----
class CustomerCreate(BaseModel):
    phone: str
    name: str = ""
    email: EmailStr | None = None
    notes: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    notes: str | None = None
    tags: str | None = None


class CustomerOut(ORMModel):
    id: str
    phone: str
    name: str
    email: str | None
    tags: str | None
    notes: str | None
    created_at: datetime | None = None


# ---- Orders ----
class OrderCreate(BaseModel):
    customer_id: str | None = None
    note: str | None = None


class OrderLineAdd(BaseModel):
    product_id: str
    qty: int = Field(default=1, ge=1)


class OrderLineUpdate(BaseModel):
    qty: int | None = Field(default=None, ge=1)
    line_discount: Decimal | None = Field(default=None, ge=0)


class OrderUpdate(BaseModel):
    customer_id: str | None = None
    note: str | None = None
    discount_percent: Decimal | None = Field(default=None, ge=0, le=100)


class PayRequest(BaseModel):
    method: Literal["cash", "card", "ewallet"] = "cash"
    amount: Decimal | None = None
    ref: str | None = None
    auto_create_customer_phone: str | None = None
    redeem_points: int = 0
    promo_code: str | None = None


class OfflineLineIn(BaseModel):
    product_id: str
    qty: int = Field(default=1, ge=1)
    unit_price: Decimal | None = None


class OfflineOrderIn(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=64)
    customer_phone: str | None = None
    customer_id: str | None = None
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    note: str | None = None
    lines: list[OfflineLineIn]
    pay_method: Literal["cash", "card", "ewallet"] = "cash"
    created_at: str | None = None


class OfflineSyncRequest(BaseModel):
    orders: list[OfflineOrderIn]


class OrderLineOut(ORMModel):
    id: str
    product_id: str
    product_name: str
    qty: int
    unit_price: Decimal
    line_discount: Decimal
    line_total: Decimal


class PaymentOut(ORMModel):
    id: str
    method: str
    amount: Decimal
    ref: str | None
    created_at: datetime | None = None


class OrderOut(ORMModel):
    id: str
    store_id: str
    user_id: str
    customer_id: str | None
    status: str
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    discount_percent: Decimal
    note: str | None
    paid_at: datetime | None
    created_at: datetime | None = None
    lines: list[OrderLineOut] = []
    payments: list[PaymentOut] = []
