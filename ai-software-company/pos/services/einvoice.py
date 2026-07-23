from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from pos.models.integrations import EInvoice, InvoiceStatus
from pos.models.orders import Order


def issue_einvoice(
    db: Session,
    order: Order,
    *,
    tax_code: str | None = None,
    buyer_name: str | None = None,
) -> EInvoice:
    """Create e-invoice stub snapshot for a paid/refunded order."""
    existing = db.query(EInvoice).filter(EInvoice.order_id == order.id).first()
    if existing and existing.status == InvoiceStatus.issued:
        return existing

    inv_no = f"EINV-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    payload = {
        "order_id": order.id,
        "store_id": order.store_id,
        "total": str(order.total),
        "subtotal": str(order.subtotal),
        "discount": str(order.discount),
        "tax": str(order.tax),
        "lines": [
            {
                "product_name": ln.product_name,
                "qty": ln.qty,
                "unit_price": str(ln.unit_price),
                "line_total": str(ln.line_total),
            }
            for ln in order.lines
        ],
        "issued_at": datetime.now(UTC).isoformat(),
        "provider": "stub-vn-einvoice",
    }
    if existing:
        inv = existing
        inv.invoice_no = inv_no
        inv.tax_code = tax_code
        inv.buyer_name = buyer_name
        inv.payload = json.dumps(payload, ensure_ascii=False)
        inv.status = InvoiceStatus.issued
    else:
        inv = EInvoice(
            order_id=order.id,
            store_id=order.store_id,
            invoice_no=inv_no,
            status=InvoiceStatus.issued,
            tax_code=tax_code,
            buyer_name=buyer_name,
            payload=json.dumps(payload, ensure_ascii=False),
        )
        db.add(inv)
    db.flush()
    return inv
