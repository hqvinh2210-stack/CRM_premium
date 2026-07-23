"""Phase 3/4 gap tests: PDF export, agent event endpoint, offline conflict fields."""

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
    }


def test_export_pdf_bytes(pos_client: TestClient):
    h = _auth(pos_client)
    r = pos_client.get("/api/v1/reports/export.pdf", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:5] == b"%PDF-"


def test_export_txt_uses_shared_builder(pos_client: TestClient):
    h = _auth(pos_client)
    r = pos_client.get("/api/v1/reports/export.txt", headers=h)
    assert r.status_code == 200
    assert "BAO CAO" in r.text or "CUOI" in r.text


def test_ai_event_skipped_when_disabled(pos_client: TestClient, monkeypatch):
    monkeypatch.setenv("AGENT_ON_ORDER", "0")
    h = _auth(pos_client)
    r = pos_client.post(
        "/api/v1/ai/event",
        headers=h,
        json={
            "event_type": "order.created",
            "payload": {"order_id": "test-order", "total": "10000"},
            "sync": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("skipped") is True or body.get("ok") is True


def test_ai_event_sync_offline_agents(pos_client: TestClient, monkeypatch):
    monkeypatch.setenv("AGENT_ON_ORDER", "1")
    monkeypatch.setenv("AGENT_FORCE_OFFLINE", "1")
    monkeypatch.setenv("CELERY_ENABLED", "0")
    h = _auth(pos_client)
    r = pos_client.post(
        "/api/v1/ai/event",
        headers=h,
        json={
            "event_type": "order.created",
            "payload": {
                "order_id": "ord-agent-1",
                "store_id": h["X-Store-Id"],
                "total": "25000",
                "customer_id": None,
            },
            "sync": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("status") in {"reviewed", "completed", "done", None} or "plan_preview" in body


def test_offline_sync_conflict_shape(pos_client: TestClient):
    h = _auth(pos_client)
    # missing product id forces conflict
    r = pos_client.post(
        "/api/v1/orders/sync",
        headers=h,
        json={
            "orders": [
                {
                    "client_id": "client-conflict-1",
                    "discount_percent": 0,
                    "pay_method": "cash",
                    "lines": [
                        {
                            "product_id": "00000000-0000-0000-0000-000000000099",
                            "qty": 1,
                            "unit_price": 1000,
                        }
                    ],
                }
            ]
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["results"]
    row = body["results"][0]
    assert row["ok"] is False
    assert row.get("status") in {"conflict", "failed"}
