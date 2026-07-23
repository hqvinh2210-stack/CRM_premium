"""Unified payment intent create / capture for VN gateways."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from pos.models.orders import Order, PaymentMethod
from pos.models.payments_ext import IntentStatus, PaymentIntent
from pos.services.orders import atomic_pay
from pos.services.payments import momo, vnpay


def _txn_ref(provider: str) -> str:
    return f"{provider[:2].upper()}{uuid.uuid4().hex[:14].upper()}"


def create_gateway_intent(
    db: Session,
    order: Order,
    *,
    provider: str,
    return_url: str | None = None,
    client_ip: str = "127.0.0.1",
) -> PaymentIntent:
    provider = provider.lower()
    txn = _txn_ref(provider)
    amount = order.total if isinstance(order.total, Decimal) else Decimal(str(order.total))

    if provider == "cash":
        intent = PaymentIntent(
            order_id=order.id,
            store_id=order.store_id,
            provider="cash",
            amount=amount,
            status=IntentStatus.created,
            txn_ref=txn,
        )
        db.add(intent)
        db.flush()
        atomic_pay(
            db,
            order,
            method=PaymentMethod.cash,
            amount=amount,
            ref=f"cash:{txn}",
            idempotency_key=f"intent:{intent.id}",
        )
        intent.status = IntentStatus.captured
        db.add(intent)
        db.commit()
        db.refresh(intent)
        return intent

    if provider == "vnpay":
        built = vnpay.build_payment_url(
            amount=amount,
            txn_ref=txn,
            order_info=f"POS order {order.id[:8]}",
            client_ip=client_ip,
            return_url=return_url,
        )
    elif provider == "momo":
        built = momo.create_payment(
            amount=amount,
            order_id=order.id,
            order_info=f"POS order {order.id[:8]}",
            txn_ref=txn,
            return_url=return_url,
        )
    elif provider == "zalopay":
        # Lightweight ZaloPay-compatible signed payload (sandbox shape)
        built = {
            "provider": "zalopay",
            "checkout_url": (
                f"https://sb-openapi.zalopay.vn/v2/pay?app_trans_id={txn}"
                f"&amount={int(amount)}&desc=POS+{order.id[:8]}"
            ),
            "txn_ref": txn,
            "signed_payload": f"zalopay|{txn}|{amount}",
            "demo_mode": True,
            "return_url": return_url,
            "ipn_url": None,
            "raw_request": {"app_trans_id": txn, "amount": str(amount)},
            "message": "ZaloPay sandbox shell — configure ZALOPAY_* for production",
        }
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    intent = PaymentIntent(
        order_id=order.id,
        store_id=order.store_id,
        provider=provider,
        amount=amount,
        status=IntentStatus.requires_action,
        txn_ref=built.get("txn_ref") or txn,
        checkout_url=built.get("checkout_url"),
        provider_trans_id=built.get("provider_trans_id"),
        return_url=built.get("return_url") or return_url,
        ipn_url=built.get("ipn_url"),
        raw_request=json.dumps(built.get("raw_request"), default=str, ensure_ascii=False)
        if built.get("raw_request")
        else None,
        raw_response=json.dumps(built.get("raw_response"), default=str, ensure_ascii=False)
        if built.get("raw_response")
        else None,
        signed_payload=built.get("signed_payload") or built.get("secure_hash"),
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)
    return intent


def verify_and_capture(
    db: Session,
    *,
    provider: str,
    intent: PaymentIntent,
    order: Order,
    query_or_body: dict | None = None,
    skip_verify: bool = False,
) -> PaymentIntent:
    if intent.status == IntentStatus.captured:
        return intent
    provider = provider.lower()
    query_or_body = query_or_body or {}

    if not skip_verify:
        if provider == "vnpay":
            ok, reason = vnpay.verify_return({str(k): str(v) for k, v in query_or_body.items()})
            if not ok:
                intent.status = IntentStatus.failed
                intent.raw_response = json.dumps({"verify": reason, **query_or_body}, default=str)
                db.add(intent)
                db.commit()
                raise ValueError(f"VNPay verify failed: {reason}")
        elif provider == "momo":
            ok, reason = momo.verify_ipn(query_or_body)
            if not ok and not (
                # allow capture endpoint with manager auth without full IPN fields in demo
                query_or_body.get("resultCode") in (0, "0", None)
                and query_or_body.get("force_capture")
            ):
                if not query_or_body.get("force_capture"):
                    intent.status = IntentStatus.failed
                    intent.raw_response = json.dumps({"verify": reason, **query_or_body}, default=str)
                    db.add(intent)
                    db.commit()
                    raise ValueError(f"MoMo verify failed: {reason}")

    atomic_pay(
        db,
        order,
        method=PaymentMethod.ewallet,
        amount=intent.amount,
        ref=f"{provider}:{intent.txn_ref}",
        idempotency_key=f"intent:{intent.id}",
    )
    intent.status = IntentStatus.captured
    if query_or_body:
        intent.raw_response = json.dumps(query_or_body, default=str, ensure_ascii=False)[:8000]
        intent.provider_trans_id = str(
            query_or_body.get("vnp_TransactionNo")
            or query_or_body.get("transId")
            or intent.provider_trans_id
            or ""
        ) or intent.provider_trans_id
    db.add(intent)
    db.commit()
    db.refresh(intent)
    return intent
