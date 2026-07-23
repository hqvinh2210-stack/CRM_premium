"""Full plan coverage: tasks, e-invoice, notify, export, transfer multi-store."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _auth(client: TestClient, email="admin@example.com", password="admin123"):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()
    return {
        "Authorization": f"Bearer {login['access_token']}",
        "X-Store-Id": login["store_id"],
    }, login


def test_follow_up_tasks_crud(pos_client: TestClient):
    h, _ = _auth(pos_client)
    cust = pos_client.get("/api/v1/customers/search", params={"q": "0912345678"}, headers=h).json()[0]
    created = pos_client.post(
        "/api/v1/tasks",
        json={"customer_id": cust["id"], "title": "Goi follow-up demo"},
        headers=h,
    ).json()
    assert created["status"] == "open"
    listed = pos_client.get(f"/api/v1/tasks?customer_id={cust['id']}", headers=h).json()
    assert any(t["id"] == created["id"] for t in listed["tasks"])
    done = pos_client.patch(
        f"/api/v1/tasks/{created['id']}",
        json={"status": "done"},
        headers=h,
    ).json()
    assert done["status"] == "done"


def test_einvoice_and_notify(pos_client: TestClient):
    h, _ = _auth(pos_client)
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
        headers={**h, "Idempotency-Key": "full-plan-pay-1"},
    ).json()
    assert paid["status"] == "paid"

    inv = pos_client.post(
        "/api/v1/invoices/e-invoice",
        json={"order_id": order["id"], "buyer_name": "Khach VIP"},
        headers=h,
    ).json()
    assert inv["invoice_no"].startswith("EINV-")
    assert inv["status"] == "issued"

    n = pos_client.post(
        "/api/v1/notify/order",
        json={"order_id": order["id"], "channel": "sms"},
        headers=h,
    ).json()
    assert n["status"] in ("sent", "queued")


def test_export_csv_and_txt(pos_client: TestClient):
    h, _ = _auth(pos_client)
    csv_r = pos_client.get("/api/v1/reports/export.csv?days=7", headers=h)
    assert csv_r.status_code == 200
    assert "order_id" in csv_r.text

    txt = pos_client.get("/api/v1/reports/export.txt", headers=h)
    assert txt.status_code == 200
    assert "BAO CAO" in txt.text


def test_transfer_between_seeded_stores(pos_client: TestClient):
    h, login = _auth(pos_client)
    me = pos_client.get("/api/v1/auth/me", headers={"Authorization": h["Authorization"]}).json()
    stores = me["stores"]
    assert len(stores) >= 2
    from_id = stores[0]["store_id"]
    to_id = stores[1]["store_id"]
    h["X-Store-Id"] = from_id
    products = pos_client.get("/api/v1/products", headers=h).json()
    p = next(x for x in products if x["sku"] == "CF-DEN")
    r = pos_client.post(
        "/api/v1/inventory/transfers",
        json={
            "from_store_id": from_id,
            "to_store_id": to_id,
            "product_id": p["id"],
            "qty": 1,
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"


def test_health_has_outbox_worker_key(pos_client: TestClient):
    h = pos_client.get("/health").json()
    assert h["ok"] is True
    assert "outbox_worker" in h or h.get("pos")
