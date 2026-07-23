from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from pos.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    issued = "issued"
    void = "void"


class EInvoice(Base):
    """E-invoice stub (P3-M5-T2)."""

    __tablename__ = "e_invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    order_id: Mapped[str] = mapped_column(String(36), index=True)
    store_id: Mapped[str] = mapped_column(String(36), index=True)
    invoice_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.draft)
    tax_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    buyer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON snapshot
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotifyChannel(str, enum.Enum):
    sms = "sms"
    zalo = "zalo"
    email = "email"


class NotifyStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    failed = "failed"


class NotificationLog(Base):
    """SMS/Zalo notify stub (P3-M5-T3)."""

    __tablename__ = "notification_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    channel: Mapped[NotifyChannel] = mapped_column(Enum(NotifyChannel))
    recipient: Mapped[str] = mapped_column(String(128), index=True)
    template: Mapped[str] = mapped_column(String(64), default="order_receipt")
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[NotifyStatus] = mapped_column(Enum(NotifyStatus), default=NotifyStatus.queued)
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
