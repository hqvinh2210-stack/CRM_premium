from __future__ import annotations

import os

from sqlalchemy.orm import Session

from pos.models.integrations import NotificationLog, NotifyChannel, NotifyStatus
from pos.models.orders import Order


def queue_order_notify(db: Session, order: Order, *, phone: str | None = None) -> NotificationLog | None:
    """
    Stub SMS/Zalo on order paid. Always logs; 'sends' if NOTIFY_STUB_SEND=1 (default on).
    """
    if not phone and not order.customer_id:
        return None
    recipient = phone or ""
    if not recipient and order.customer_id:
        from pos.models.customers import Customer

        c = db.get(Customer, order.customer_id)
        recipient = (c.phone if c else "") or ""
    if not recipient:
        return None

    channel_name = os.getenv("NOTIFY_CHANNEL", "sms").lower()
    channel = NotifyChannel.zalo if channel_name == "zalo" else NotifyChannel.sms
    body = (
        f"[POS] Cam on quy khach. Don {order.id[:8]} "
        f"tong {order.total} VND da thanh toan."
    )
    log = NotificationLog(
        channel=channel,
        recipient=recipient,
        template="order_receipt",
        body=body,
        status=NotifyStatus.queued,
        ref_type="order",
        ref_id=order.id,
    )
    db.add(log)
    db.flush()

    # stub send
    if os.getenv("NOTIFY_STUB_SEND", "1") == "1":
        log.status = NotifyStatus.sent
    return log
