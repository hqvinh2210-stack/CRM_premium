"""Cashier shift open/close (Phase 5)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from pos.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ShiftStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class CashShift(Base):
    __tablename__ = "cash_shifts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    status: Mapped[ShiftStatus] = mapped_column(
        Enum(ShiftStatus), default=ShiftStatus.open, index=True
    )
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    closing_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    expected_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    variance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
