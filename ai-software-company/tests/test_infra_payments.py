"""Postgres/Alembic helpers, VNPay/MoMo signing, payment intents."""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from pos.services.payments import momo, vnpay


def _auth(client: TestClient):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin123"},
    ).json()
    return {
        "Authorization": f"Bearer {login['access_token']}",
        "X-Store-Id": login["store_id"],
    }


def test_vnpay_sign_and_verify_roundtrip():
    built = vnpay.build_payment_url(
        amount=Decimal("50000"),
        txn_ref="VNTEST001",
        order_info="Test order",
        client_ip="127.0.0.1",
    )
    assert "vnp_SecureHash" in built["raw_request"]
    assert built["checkout_url"].startswith("https://")
    # Reconstruct query from raw_request for verify
    q = {k: str(v) for k, v in built["raw_request"].items()}
    # Simulate successful return
    q["vnp_ResponseCode"] = "00"
    # Re-sign after adding response code
    from pos.services.payments.vnpay import _cfg, _hmac_sha512

    data = {k: v for k, v in q.items() if k != "vnp_SecureHash"}
    sign = "&".join(f"{k}={v}" for k, v in sorted(data.items()))
    q["vnp_SecureHash"] = _hmac_sha512(_cfg()["hash_secret"], sign)
    ok, reason = vnpay.verify_return(q)
    assert ok, reason


def test_momo_signature_present():
    built = momo.build_create_payload(
        amount=Decimal("25000"),
        order_id="MOMOTEST001",
        order_info="Coffee",
        request_id="MOMOTEST001",
    )
    assert built["signature"]
    assert len(built["signature"]) == 64
    assert built["body"]["signature"] == built["signature"]


def test_payment_intent_vnpay_and_capture(pos_client: TestClient):
    h = _auth(pos_client)
    products = pos_client.get("/api/v1/products", headers=h).json()
    p = products[0]
    order = pos_client.post("/api/v1/orders", json={}, headers=h).json()
    pos_client.post(
        f"/api/v1/orders/{order['id']}/lines",
        json={"product_id": p["id"], "qty": 1},
        headers=h,
    )
    intent = pos_client.post(
        "/api/v1/payments/intent",
        json={"order_id": order["id"], "provider": "vnpay"},
        headers=h,
    ).json()
    assert intent["status"] == "requires_action"
    assert intent["checkout_url"]
    assert "vnp_" in intent["checkout_url"] or "vnpay" in intent["checkout_url"].lower()

    cap = pos_client.post(
        "/api/v1/payments/capture",
        json={
            "intent_id": intent["intent_id"],
            "order_id": order["id"],
            "provider": "vnpay",
            "force_capture": True,
        },
        headers=h,
    ).json()
    assert cap["status"] == "captured"

    # order paid
    o2 = pos_client.get(f"/api/v1/orders/{order['id']}", headers=h).json()
    assert o2["status"] == "paid"


def test_payment_intent_momo(pos_client: TestClient):
    h = _auth(pos_client)
    products = pos_client.get("/api/v1/products", headers=h).json()
    p = products[0]
    order = pos_client.post("/api/v1/orders", json={}, headers=h).json()
    pos_client.post(
        f"/api/v1/orders/{order['id']}/lines",
        json={"product_id": p["id"], "qty": 1},
        headers=h,
    )
    intent = pos_client.post(
        "/api/v1/payments/intent",
        json={"order_id": order["id"], "provider": "momo"},
        headers=h,
    ).json()
    assert intent["provider"] == "momo"
    assert intent["checkout_url"]
    assert intent["status"] == "requires_action"


def test_db_backend_and_alembic_import():
    from pos.db import db_backend, run_alembic_upgrade

    assert db_backend() in {"sqlite", "postgresql", "other"}
    # import path for alembic config must exist
    from pathlib import Path

    assert (Path(__file__).resolve().parents[1] / "alembic.ini").exists()
    assert callable(run_alembic_upgrade)


def test_celery_eager_outbox():
    import os

    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "1"
    # re-import conf
    from workers.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    from workers.tasks import process_outbox_batch

    result = process_outbox_batch.apply(args=(10,)).get()
    assert "processed" in result or "via" in result
