"""Phase 5: metrics, shifts, backup, excel export."""

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


def test_ops_metrics(pos_client: TestClient):
    h = _auth(pos_client)
    r = pos_client.get("/api/v1/ops/metrics", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "orders_today" in body
    assert "revenue_today" in body
    assert "outbox" in body


def test_shift_open_close(pos_client: TestClient):
    h = _auth(pos_client, "cashier@example.com", "cashier123")
    # close any existing open shift as admin first if needed
    cur = pos_client.get("/api/v1/shifts/current", headers=h).json()
    if cur.get("shift"):
        pos_client.post(
            f"/api/v1/shifts/{cur['shift']['id']}/close",
            headers=h,
            json={"closing_cash": 0},
        )

    opened = pos_client.post(
        "/api/v1/shifts/open",
        headers=h,
        json={"opening_cash": 100000, "note": "morning"},
    )
    assert opened.status_code == 200, opened.text
    shift = opened.json()
    assert shift["status"] == "open"
    assert float(shift["opening_cash"]) == 100000

    # second open should fail
    again = pos_client.post(
        "/api/v1/shifts/open",
        headers=h,
        json={"opening_cash": 0},
    )
    assert again.status_code == 400

    closed = pos_client.post(
        f"/api/v1/shifts/{shift['id']}/close",
        headers=h,
        json={"closing_cash": 150000, "note": "eod"},
    )
    assert closed.status_code == 200
    body = closed.json()
    assert body["status"] == "closed"
    assert body["variance"] is not None


def test_ops_audit_and_staff(pos_client: TestClient):
    h = _auth(pos_client)
    audit = pos_client.get("/api/v1/ops/audit?limit=10", headers=h)
    assert audit.status_code == 200
    assert "items" in audit.json()

    staff = pos_client.get("/api/v1/ops/staff", headers=h)
    assert staff.status_code == 200
    assert len(staff.json()["staff"]) >= 1


def test_backup_and_xlsx(pos_client: TestClient):
    h = _auth(pos_client)
    bak = pos_client.get("/api/v1/ops/backup.json", headers=h)
    assert bak.status_code == 200
    data = bak.json()
    assert "products" in data
    assert data["version"] == "0.8.0"

    xls = pos_client.get("/api/v1/reports/export.xlsx?days=7", headers=h)
    assert xls.status_code == 200
    assert b"Workbook" in xls.content or b"Excel" in xls.content


def test_cashier_cannot_backup(pos_client: TestClient):
    h = _auth(pos_client, "cashier@example.com", "cashier123")
    r = pos_client.get("/api/v1/ops/backup.json", headers=h)
    assert r.status_code == 403
