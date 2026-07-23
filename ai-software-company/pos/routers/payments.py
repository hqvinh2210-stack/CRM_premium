from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import AuthContext, require_any
from pos.models.orders import Order
from pos.models.payments_ext import IntentStatus, PaymentIntent
from pos.routers.orders import _load_order
from pos.services.payments.gateway import create_gateway_intent, verify_and_capture

router = APIRouter(prefix="/payments", tags=["payments"])


class IntentIn(BaseModel):
    order_id: str
    provider: str = Field(description="vnpay|momo|zalopay|cash")
    return_url: str | None = None


def _intent_out(intent: PaymentIntent) -> dict:
    return {
        "id": intent.id,
        "intent_id": intent.id,
        "provider": intent.provider,
        "order_id": intent.order_id,
        "amount": str(intent.amount),
        "status": intent.status.value,
        "txn_ref": intent.txn_ref,
        "checkout_url": intent.checkout_url,
        "return_url": intent.return_url,
        "ipn_url": intent.ipn_url,
        "provider_trans_id": intent.provider_trans_id,
        "demo_signed": bool(intent.signed_payload),
    }


@router.post("/intent")
def create_payment_intent(
    body: IntentIn,
    request: Request,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    """
    Create payment intent.
    - cash: capture immediately
    - vnpay/momo: HMAC-signed sandbox checkout URL (real protocol)
    """
    order = _load_order(db, body.order_id, ctx.store_id)
    provider = body.provider.lower()
    if provider not in {"vnpay", "momo", "zalopay", "cash"}:
        raise HTTPException(400, "Unsupported provider")
    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        intent = create_gateway_intent(
            db,
            order,
            provider=provider,
            return_url=body.return_url,
            client_ip=client_ip,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    out = _intent_out(intent)
    if intent.status == IntentStatus.captured:
        out["message"] = "Cash captured"
    else:
        out["message"] = "Redirect customer to checkout_url; complete via IPN/return or /payments/capture"
    return out


class CaptureIn(BaseModel):
    intent_id: str | None = None
    txn_ref: str | None = None
    order_id: str
    provider: str
    force_capture: bool = Field(
        default=False,
        description="Manager/demo: skip full gateway signature (sandbox complete)",
    )


@router.post("/capture")
def capture_payment(
    body: CaptureIn,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    order = _load_order(db, body.order_id, ctx.store_id)
    intent = None
    if body.intent_id:
        intent = db.get(PaymentIntent, body.intent_id)
    if not intent and body.txn_ref:
        intent = db.query(PaymentIntent).filter(PaymentIntent.txn_ref == body.txn_ref).first()
    if not intent:
        # backward-compat: fabricate capture without stored intent
        from pos.models.orders import PaymentMethod
        from pos.services.orders import atomic_pay

        paid = atomic_pay(
            db,
            order,
            method=PaymentMethod.ewallet if body.provider != "cash" else PaymentMethod.cash,
            amount=order.total,
            ref=f"{body.provider}:{body.intent_id or body.txn_ref or 'manual'}",
            idempotency_key=f"intent:{body.intent_id or body.txn_ref or order.id}",
        )
        return {"status": "captured", "order_id": paid.id, "total": str(paid.total)}

    if intent.store_id != ctx.store_id or intent.order_id != order.id:
        raise HTTPException(404, "Intent not found for order/store")
    try:
        payload = {"force_capture": body.force_capture, "resultCode": "0"}
        captured = verify_and_capture(
            db,
            provider=body.provider,
            intent=intent,
            order=order,
            query_or_body=payload,
            skip_verify=body.force_capture or body.provider == "cash",
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "status": captured.status.value,
        "order_id": order.id,
        "total": str(order.total),
        "intent_id": captured.id,
        "txn_ref": captured.txn_ref,
    }


@router.get("/intents/{intent_id}")
def get_intent(
    intent_id: str,
    ctx: AuthContext = Depends(require_any("cashier", "manager", "admin")),
    db: Session = Depends(get_db),
):
    intent = db.get(PaymentIntent, intent_id)
    if not intent or intent.store_id != ctx.store_id:
        raise HTTPException(404, "Not found")
    return _intent_out(intent)


# ---- VNPay return / IPN (public) ----


@router.get("/vnpay/return")
def vnpay_return(request: Request, db: Session = Depends(get_db)):
    params = {k: v for k, v in request.query_params.items()}
    return _vnpay_complete(db, params, source="return")


@router.get("/vnpay/ipn")
def vnpay_ipn(request: Request, db: Session = Depends(get_db)):
    params = {k: v for k, v in request.query_params.items()}
    result = _vnpay_complete(db, params, source="ipn")
    # VNPay expects RspCode
    if result.get("ok"):
        return {"RspCode": "00", "Message": "Confirm Success"}
    return {"RspCode": "97", "Message": result.get("error", "Fail")}


def _vnpay_complete(db: Session, params: dict, *, source: str) -> dict:
    from pos.services.payments import vnpay

    txn_ref = params.get("vnp_TxnRef") or ""
    intent = db.query(PaymentIntent).filter(PaymentIntent.txn_ref == txn_ref).first()
    if not intent:
        return {"ok": False, "error": "intent_not_found", "source": source}
    order = db.get(Order, intent.order_id)
    if not order:
        return {"ok": False, "error": "order_not_found", "source": source}
    ok, reason = vnpay.verify_return(params)
    if not ok:
        intent.status = IntentStatus.failed
        db.add(intent)
        db.commit()
        return {"ok": False, "error": reason, "source": source}
    try:
        verify_and_capture(
            db,
            provider="vnpay",
            intent=intent,
            order=order,
            query_or_body=params,
            skip_verify=True,  # already verified
        )
        return {"ok": True, "order_id": order.id, "status": "captured", "source": source}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "source": source}


# ---- MoMo return / IPN ----


@router.get("/momo/return")
def momo_return(
    orderId: str | None = Query(default=None),
    resultCode: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return {"orderId": orderId, "resultCode": resultCode, "message": "Return received — check IPN/capture"}


@router.post("/momo/ipn")
async def momo_ipn(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
    except Exception:
        body = dict(await request.form())  # type: ignore[arg-type]
    body = {str(k): v for k, v in body.items()}
    txn_ref = str(body.get("orderId") or body.get("requestId") or "")
    intent = db.query(PaymentIntent).filter(PaymentIntent.txn_ref == txn_ref).first()
    if not intent:
        return {"resultCode": 1001, "message": "intent not found"}
    order = db.get(Order, intent.order_id)
    if not order:
        return {"resultCode": 1002, "message": "order not found"}
    try:
        verify_and_capture(
            db,
            provider="momo",
            intent=intent,
            order=order,
            query_or_body=body,
            skip_verify=False,
        )
        return {"resultCode": 0, "message": "success"}
    except ValueError as exc:
        # allow demo force when resultCode 0
        if str(body.get("resultCode")) == "0":
            try:
                verify_and_capture(
                    db,
                    provider="momo",
                    intent=intent,
                    order=order,
                    query_or_body={**body, "force_capture": True},
                    skip_verify=True,
                )
                return {"resultCode": 0, "message": "success_demo"}
            except Exception as exc2:  # noqa: BLE001
                return {"resultCode": 1003, "message": str(exc2)}
        return {"resultCode": 1004, "message": str(exc)}
