"""Phase 1 POS integration tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _login(client: TestClient, email="cashier@example.com", password="cashier123"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    data = r.json()
    return data["access_token"], data["store_id"]


def test_login_and_me(pos_client: TestClient):
    token, store_id = _login(pos_client)
    r = pos_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "cashier@example.com"
    assert store_id


def test_list_products(pos_client: TestClient):
    token, store_id = _login(pos_client)
    r = pos_client.get(
        "/api/v1/products",
        headers={"Authorization": f"Bearer {token}", "X-Store-Id": store_id},
    )
    assert r.status_code == 200
    assert len(r.json()) >= 4


def test_full_checkout_flow(pos_client: TestClient):
    token, store_id = _login(pos_client)
    h = {"Authorization": f"Bearer {token}", "X-Store-Id": store_id}

    products = pos_client.get("/api/v1/products", headers=h).json()
    coffee = next(p for p in products if p["sku"] == "CF-DEN")
    stock_before = coffee["stock_qty"]

    order = pos_client.post("/api/v1/orders", json={}, headers=h).json()
    order = pos_client.post(
        f"/api/v1/orders/{order['id']}/lines",
        json={"product_id": coffee["id"], "qty": 2},
        headers=h,
    ).json()
    assert float(order["total"]) == 50000.0

    customers = pos_client.get(
        "/api/v1/customers/search", params={"q": "0912345678"}, headers=h
    ).json()
    order = pos_client.patch(
        f"/api/v1/orders/{order['id']}",
        json={"customer_id": customers[0]["id"], "discount_percent": 10},
        headers=h,
    ).json()
    assert float(order["total"]) == 45000.0

    paid = pos_client.post(
        f"/api/v1/orders/{order['id']}/pay",
        json={"method": "cash"},
        headers={**h, "Idempotency-Key": "test-pay-checkout-1"},
    ).json()
    assert paid["status"] == "paid"

    products2 = pos_client.get("/api/v1/products", headers=h).json()
    coffee2 = next(p for p in products2 if p["sku"] == "CF-DEN")
    assert coffee2["stock_qty"] == stock_before - 2

    receipt = pos_client.get(f"/api/v1/orders/{order['id']}/receipt", headers=h).json()
    assert "HOA DON" in receipt["text"]

    report = pos_client.get("/api/v1/reports/daily-sales", headers=h).json()
    assert report["order_count"] >= 1


def test_rbac_cashier_cannot_create_product(pos_client: TestClient):
    token, store_id = _login(pos_client)
    r = pos_client.post(
        "/api/v1/products",
        headers={"Authorization": f"Bearer {token}", "X-Store-Id": store_id},
        json={"sku": "X-RBAC", "name": "X", "price": 1},
    )
    assert r.status_code == 403
