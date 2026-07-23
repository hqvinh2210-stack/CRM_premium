# Phase 5 — Ops & Growth (v0.8)

Sau Phase 1–4 (POS/CRM full + SoftPOS), Phase 5 bổ sung vận hành quầy và ops.

## Modules

| ID | Feature | API / UI |
|----|---------|----------|
| P5-M1 | Live metrics | `GET /api/v1/ops/metrics` · tab **Ops** |
| P5-M2 | JSON backup (admin) | `GET /api/v1/ops/backup.json` |
| P5-M3 | Cash shift open/close | `POST /api/v1/shifts/open`, `.../close` |
| P5-M4 | Excel SpreadsheetML | `GET /api/v1/reports/export.xlsx` |
| P5-M5 | Audit list | `GET /api/v1/ops/audit` |
| P5-M6 | Staff list | `GET /api/v1/ops/staff` |

## UI

Mở http://127.0.0.1:8001 → đăng nhập → tab **Ops**

- Mở ca / đóng ca (đếm tiền, variance)
- Metrics hôm nay, outbox, low stock
- Manager: staff + audit
- Admin: backup JSON; manager: Excel 7 ngày

## Login

Chỉ email + mật khẩu (same-origin Docker SPA).

- `cashier@example.com` / `cashier123`
- `admin@example.com` / `admin123`
