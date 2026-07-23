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


class IntentStatus(str, enum.Enum):
    created = "created"
    requires_action = "requires_action"
    pending = "pending"
    captured = "captured"
    failed = "failed"
    expired = "expired"


class PaymentIntent(Base):
    """Gateway payment intent (VNPay / MoMo / ZaloPay sandbox)."""

    __tablename__ = "payment_intents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    store_id: Mapped[str] = mapped_column(String(36), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)  # vnpay|momo|zalopay|cash
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[IntentStatus] = mapped_column(Enum(IntentStatus), default=IntentStatus.created)
    txn_ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_trans_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    return_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ipn_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_request: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
