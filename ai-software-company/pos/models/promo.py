from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from pos.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class PromoType(str, enum.Enum):
    percent = "percent"
    fixed = "fixed"
    coupon = "coupon"
    bxgy = "bxgy"  # buy X get Y free (simple: buy_qty / free_qty on any)


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    promo_type: Mapped[PromoType] = mapped_column(Enum(PromoType), default=PromoType.percent)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)  # % or fixed amount
    min_subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    buy_qty: Mapped[int] = mapped_column(Integer, default=0)
    free_qty: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
