"""
VNPay sandbox adapter (HMAC-SHA512).

Docs: https://sandbox.vnpayment.vn/apis/docs/thanh-toan-pay/pay.html
Env:
  VNPAY_TMN_CODE
  VNPAY_HASH_SECRET
  VNPAY_URL (default sandbox pay URL)
  VNPAY_RETURN_URL
  VNPAY_IPN_URL
  PUBLIC_BASE_URL (fallback for return/ipn)
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime
from decimal import Decimal
from urllib.parse import quote_plus, urlencode


def _cfg() -> dict:
    base = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
    return {
        "tmn_code": os.getenv("VNPAY_TMN_CODE", "DEMO"),
        "hash_secret": os.getenv("VNPAY_HASH_SECRET", "DEMOSECRET"),
        "pay_url": os.getenv(
            "VNPAY_URL",
            "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
        ),
        "return_url": os.getenv("VNPAY_RETURN_URL", f"{base}/api/v1/payments/vnpay/return"),
        "ipn_url": os.getenv("VNPAY_IPN_URL", f"{base}/api/v1/payments/vnpay/ipn"),
        # When DEMO credentials: still produce valid signed URL for local tests
        "demo_mode": os.getenv("VNPAY_TMN_CODE", "DEMO") in {"", "DEMO"}
        or os.getenv("VNPAY_HASH_SECRET", "DEMOSECRET") in {"", "DEMOSECRET"},
    }


def _hmac_sha512(key: str, data: str) -> str:
    return hmac.new(key.encode("utf-8"), data.encode("utf-8"), hashlib.sha512).hexdigest()


def build_payment_url(
    *,
    amount: Decimal,
    txn_ref: str,
    order_info: str,
    client_ip: str = "127.0.0.1",
    return_url: str | None = None,
) -> dict:
    cfg = _cfg()
    create_date = datetime.now().strftime("%Y%m%d%H%M%S")
    # VNPay amount is VND * 100
    amount_i = int(amount.quantize(Decimal("1")) * 100)
    params: dict[str, str] = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": cfg["tmn_code"],
        "vnp_Amount": str(amount_i),
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": txn_ref,
        "vnp_OrderInfo": order_info[:255],
        "vnp_OrderType": "other",
        "vnp_Locale": "vn",
        "vnp_ReturnUrl": return_url or cfg["return_url"],
        "vnp_IpAddr": client_ip,
        "vnp_CreateDate": create_date,
    }
    # Sort and hash (VNPay: hash raw query without URL-encoding for sign string)
    sorted_items = sorted(params.items())
    sign_data = "&".join(f"{k}={v}" for k, v in sorted_items)
    secure = _hmac_sha512(cfg["hash_secret"], sign_data)
    params["vnp_SecureHash"] = secure
    # Build redirect URL with encoded values
    query = urlencode(params, quote_via=quote_plus)
    checkout = f"{cfg['pay_url']}?{query}"
    return {
        "provider": "vnpay",
        "checkout_url": checkout,
        "txn_ref": txn_ref,
        "signed_payload": sign_data,
        "secure_hash": secure,
        "demo_mode": cfg["demo_mode"],
        "return_url": params["vnp_ReturnUrl"],
        "ipn_url": cfg["ipn_url"],
        "raw_request": params,
    }


def verify_return(query: dict[str, str]) -> tuple[bool, str]:
    """Verify vnp_SecureHash from return/IPN query params."""
    cfg = _cfg()
    data = {k: v for k, v in query.items() if k.startswith("vnp_") and k != "vnp_SecureHash"}
    secure = query.get("vnp_SecureHash") or query.get("vnp_secure_hash") or ""
    if not secure:
        return False, "missing_secure_hash"
    sorted_items = sorted((k, v) for k, v in data.items() if v is not None)
    sign_data = "&".join(f"{k}={v}" for k, v in sorted_items)
    expected = _hmac_sha512(cfg["hash_secret"], sign_data)
    if not hmac.compare_digest(expected.lower(), secure.lower()):
        return False, "invalid_signature"
    rsp = data.get("vnp_ResponseCode", "")
    if rsp != "00":
        return False, f"response_code_{rsp}"
    return True, "ok"
