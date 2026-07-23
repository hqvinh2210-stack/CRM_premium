"""Offline order sync endpoint."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_offline_sync_pay(pos_client: TestClient):
    login = pos_client.post(
        "/api/v1/auth/login",
        json={"email": "cashier@example.com", "password": "cashier123"},
    ).json()
    h = {
        "Authorization": f"Bearer {login['access_token']}",
        "X-Store-Id": login["store_id"],
    }
    products = pos_client.get("/api/v1/products", headers=h).json()
    p = next(x for x in products if x["sku"] == "CF-SUA")
    before = p["stock_qty"]
    client_id = f"offline-{uuid.uuid4()}"

    body = {
        "orders": [
            {
                "client_id": client_id,
                "discount_percent": 0,
                "lines": [{"product_id": p["id"], "qty": 1}],
                "pay_method": "cash",
            }
        ]
    }
    r = pos_client.post("/api/v1/orders/sync", headers=h, json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["results"][0]["ok"] is True

    r2 = pos_client.post("/api/v1/orders/sync", headers=h, json=body)
    assert r2.json()["results"][0]["status"] == "already_synced"

    products2 = pos_client.get("/api/v1/products", headers=h).json()
    p2 = next(x for x in products2 if x["sku"] == "CF-SUA")
    assert p2["stock_qty"] == before - 1
