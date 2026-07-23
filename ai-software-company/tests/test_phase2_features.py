"""Phase 2–3 feature smoke tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _auth(client: TestClient):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin123"},
    ).json()
    return {
        "Authorization": f"Bearer {login['access_token']}",
        "X-Store-Id": login["store_id"],
    }


def test_loyalty_program_and_earn(pos_client: TestClient):
    h = _auth(pos_client)
    prog = pos_client.get("/api/v1/loyalty/program", headers=h).json()
    assert prog["program"] is not None

    products = pos_client.get("/api/v1/products", headers=h).json()
    p = products[0]
    cust = pos_client.get("/api/v1/customers/search", params={"q": "0912345678"}, headers=h).json()[0]

    order = pos_client.post("/api/v1/orders", json={"customer_id": cust["id"]}, headers=h).json()
    pos_client.post(
        f"/api/v1/orders/{order['id']}/lines",
        json={"product_id": p["id"], "qty": 1},
        headers=h,
    )
    paid = pos_client.post(
        f"/api/v1/orders/{order['id']}/pay",
        json={"method": "cash"},
        headers={**h, "Idempotency-Key": "loy-earn-1"},
    ).json()
    assert paid["status"] == "paid"

    pts = pos_client.get(f"/api/v1/loyalty/points/{cust['id']}", headers=h).json()
    assert pts["balance"] >= 0  # earned based on total


def test_promo_list_and_apply(pos_client: TestClient):
    h = _auth(pos_client)
    promos = pos_client.get("/api/v1/promotions", headers=h).json()
    assert len(promos["promotions"]) >= 1

    products = pos_client.get("/api/v1/products", headers=h).json()
    p = next(x for x in products if x["sku"] == "CF-DEN")
    order = pos_client.post("/api/v1/orders", json={}, headers=h).json()
    order = pos_client.post(
        f"/api/v1/orders/{order['id']}/lines",
        json={"product_id": p["id"], "qty": 2},
        headers=h,
    ).json()
    applied = pos_client.post(
        f"/api/v1/promotions/orders/{order['id']}/apply",
        json={"code": "SALE10"},
        headers=h,
    ).json()
    assert "total" in applied


def test_low_stock_and_recommend(pos_client: TestClient):
    h = _auth(pos_client)
    low = pos_client.get("/api/v1/inventory/low-stock?threshold=1000", headers=h).json()
    assert "items" in low

    products = pos_client.get("/api/v1/products", headers=h).json()
    pid = products[0]["id"]
    rec = pos_client.get(f"/api/v1/ai/recommend?product_ids={pid}", headers=h).json()
    assert "items" in rec


def test_outbox_process(pos_client: TestClient):
    h = _auth(pos_client)
    r = pos_client.post("/api/v1/events/process", headers=h).json()
    assert "processed" in r
