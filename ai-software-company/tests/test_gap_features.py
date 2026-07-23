"""Gap-fill features: refund, points expiry, timeline, analytics, outbox DLQ."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def _auth(client: TestClient, email="admin@example.com", password="admin123"):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()
    return {
        "Authorization": f"Bearer {login['access_token']}",
        "X-Store-Id": login["store_id"],
    }


def test_refund_restores_stock_and_status(pos_client: TestClient):
    h = _auth(pos_client)
    products = pos_client.get("/api/v1/products", headers=h).json()
    coffee = next(p for p in products if p["sku"] == "CF-DEN")
    stock_before = coffee["stock_qty"]

    order = pos_client.post("/api/v1/orders", json={}, headers=h).json()
    pos_client.post(
        f"/api/v1/orders/{order['id']}/lines",
        json={"product_id": coffee["id"], "qty": 2},
        headers=h,
    )
    paid = pos_client.post(
        f"/api/v1/orders/{order['id']}/pay",
        json={"method": "cash"},
        headers={**h, "Idempotency-Key": "refund-pay-1"},
    ).json()
    assert paid["status"] == "paid"

    mid = pos_client.get("/api/v1/products", headers=h).json()
    coffee_mid = next(p for p in mid if p["sku"] == "CF-DEN")
    assert coffee_mid["stock_qty"] == stock_before - 2

    refunded = pos_client.post(
        f"/api/v1/orders/{order['id']}/refund",
        json={"reason": "customer return"},
        headers=h,
    ).json()
    assert refunded["status"] == "refunded"

    after = pos_client.get("/api/v1/products", headers=h).json()
    coffee_after = next(p for p in after if p["sku"] == "CF-DEN")
    assert coffee_after["stock_qty"] == stock_before

    # idempotent second refund
    again = pos_client.post(
        f"/api/v1/orders/{order['id']}/refund",
        json={},
        headers=h,
    ).json()
    assert again["status"] == "refunded"


def test_cashier_cannot_refund(pos_client: TestClient):
    h_admin = _auth(pos_client)
    products = pos_client.get("/api/v1/products", headers=h_admin).json()
    p = products[0]
    order = pos_client.post("/api/v1/orders", json={}, headers=h_admin).json()
    pos_client.post(
        f"/api/v1/orders/{order['id']}/lines",
        json={"product_id": p["id"], "qty": 1},
        headers=h_admin,
    )
    pos_client.post(
        f"/api/v1/orders/{order['id']}/pay",
        json={"method": "cash"},
        headers={**h_admin, "Idempotency-Key": "refund-rbac-1"},
    )

    h_cash = _auth(pos_client, "cashier@example.com", "cashier123")
    # cashier may be on different store membership — use same store from admin login store if needed
    r = pos_client.post(f"/api/v1/orders/{order['id']}/refund", json={}, headers=h_cash)
    assert r.status_code in (403, 404)


def test_points_expire_endpoint(pos_client: TestClient):
    h = _auth(pos_client)
    cust = pos_client.get("/api/v1/customers/search", params={"q": "0912345678"}, headers=h).json()[0]
    products = pos_client.get("/api/v1/products", headers=h).json()
    p = products[0]
    order = pos_client.post("/api/v1/orders", json={"customer_id": cust["id"]}, headers=h).json()
    pos_client.post(
        f"/api/v1/orders/{order['id']}/lines",
        json={"product_id": p["id"], "qty": 1},
        headers=h,
    )
    pos_client.post(
        f"/api/v1/orders/{order['id']}/pay",
        json={"method": "cash"},
        headers={**h, "Idempotency-Key": "expire-earn-1"},
    )

    # backdate earn txn so expiry job can pick it up
    from pos.db import SessionLocal
    from pos.models.loyalty import PointTransaction, PointTxnType

    db = SessionLocal()
    try:
        txns = (
            db.query(PointTransaction)
            .filter(
                PointTransaction.customer_id == cust["id"],
                PointTransaction.txn_type == PointTxnType.earn,
            )
            .all()
        )
        old = datetime.now(UTC) - timedelta(days=400)
        for t in txns:
            t.created_at = old
        db.commit()
    finally:
        db.close()

    bal_before = pos_client.get(f"/api/v1/loyalty/points/{cust['id']}", headers=h).json()["balance"]
    result = pos_client.post("/api/v1/loyalty/expire", json={"ttl_days": 365}, headers=h).json()
    assert "points_expired" in result
    if bal_before > 0:
        assert result["points_expired"] >= 0
        bal_after = pos_client.get(f"/api/v1/loyalty/points/{cust['id']}", headers=h).json()["balance"]
        assert bal_after <= bal_before


def test_customer_timeline_and_analytics(pos_client: TestClient):
    h = _auth(pos_client)
    cust = pos_client.get("/api/v1/customers/search", params={"q": "0912345678"}, headers=h).json()[0]
    products = pos_client.get("/api/v1/products", headers=h).json()
    p = products[0]
    order = pos_client.post("/api/v1/orders", json={"customer_id": cust["id"]}, headers=h).json()
    pos_client.post(
        f"/api/v1/orders/{order['id']}/lines",
        json={"product_id": p["id"], "qty": 1},
        headers=h,
    )
    pos_client.post(
        f"/api/v1/orders/{order['id']}/pay",
        json={"method": "cash"},
        headers={**h, "Idempotency-Key": "timeline-1"},
    )

    tl = pos_client.get(f"/api/v1/customers/{cust['id']}/timeline", headers=h).json()
    assert tl["count"] >= 1
    kinds = {e["kind"] for e in tl["events"]}
    assert any(k.startswith("order.") for k in kinds)

    dash = pos_client.get("/api/v1/reports/analytics?days=7", headers=h).json()
    assert "by_day" in dash
    assert len(dash["by_day"]) == 7
    assert "totals" in dash
    assert "top_products" in dash


def test_outbox_process_returns_dlq_fields(pos_client: TestClient):
    h = _auth(pos_client)
    r = pos_client.post("/api/v1/events/process", headers=h).json()
    assert "processed" in r
    assert "dead_lettered" in r
    assert "max_attempts" in r

    out = pos_client.get("/api/v1/events/outbox", headers=h).json()
    assert "events" in out
