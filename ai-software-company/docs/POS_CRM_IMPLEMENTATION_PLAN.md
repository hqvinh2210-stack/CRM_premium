# Plan implement POS + CRM (chi tiết theo phase / module)

**Repo:** `ai-software-company` + `orchestrator`  
**Delivery:** Linear issue → webhook → LangGraph (Ava plan → Rex code → Kai review)  
**Memory:** Mem0 hybrid (local + Gemini) giữ chuẩn kiến trúc  

---

## 0. Quy ước delivery (khớp setup hiện tại)

### 0.1 Template Linear Issue

```text
Title: [P{phase}-{module}] {short feature name}
Labels: phase-1|phase-2|phase-3|phase-4, module:{name}, type:feature|bug|chore
Priority: Urgent | High | Medium | Low
Description: (dùng body chuẩn bên dưới)
```

**Body chuẩn (paste vào Linear):**

```markdown
## Goal
...

## Acceptance criteria
- [ ] ...

## Schema / contracts
...

## API
...

## Frontend
...

## Business rules
...

## Tests
- [ ] unit
- [ ] integration
- [ ] e2e (nếu có)

## Out of scope
...

## Agent handoff
- Ava: plan modules + files
- Rex: implement
- Kai: review security/stock/money correctness
```

### 0.2 Definition of Done (DoD)

- [ ] Migration DB (nếu có)  
- [ ] API + OpenAPI docs  
- [ ] Tests pass  
- [ ] Memory note (chuẩn stack) nếu quyết định kiến trúc mới  
- [ ] Review APPROVE  

### 0.3 Monorepo module layout (target)

```text
ai-software-company/
  app/                 # FastAPI gateway (đã có)
  agents/ graph/ memory/  # AI delivery (đã có)
  pos/                 # NEW domain packages
    auth/
    catalog/
    orders/
    customers/
    loyalty/
    payments/
    reports/
    inventory/
  web/                 # NEW React POS
  docs/
  tests/
```

---

## Phase 1 – MVP (4–6 tuần): Core POS + CRM cơ bản

**Epic Linear:** `P1 – MVP Core POS + CRM`  
**Mục tiêu:** Bán được tại quầy, gắn khách, xem lịch sử, báo cáo ngày.

### Module P1-M1 — Auth & Multi-store

| Field | Chi tiết |
|-------|----------|
| **Goal** | Login JWT, chọn store, RBAC cashier/manager/admin |
| **Schema** | `users`, `stores`, `user_store_roles` (role enum), `refresh_tokens` |
| **API** | `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`, `GET /stores`, `POST /stores` (admin) |
| **Frontend** | `LoginPage`, `StoreSelector`, auth store (Zustand) |
| **Rules** | Password hash (argon2/bcrypt); JWT access 15m + refresh; middleware `require_role` |
| **Tests** | login ok/fail; role denied; multi-store isolation |
| **Linear tasks** | `P1-M1-T1` schema+migration · `P1-M1-T2` auth API · `P1-M1-T3` RBAC middleware · `P1-M1-T4` login UI |

### Module P1-M2 — Catalog & Inventory cơ bản

| Field | Chi tiết |
|-------|----------|
| **Goal** | CRUD SP, tìm barcode, tồn theo store |
| **Schema** | `categories`, `products` (sku, name, price, cost, barcode, track_inventory, deleted_at), `product_variants?`, `stock_levels(store_id, product_id, qty)` |
| **API** | `CRUD /products`, `GET /products/search?q=`, `GET /products/barcode/{code}`, `POST /stock/adjust` |
| **Frontend** | Product grid touch, search bar, barcode input, low-stock badge |
| **Rules** | Soft-delete; price >= 0; stock adjust có lý do; optimistic lock qty (version) |
| **Tests** | barcode unique; stock không âm khi track=true (optional warn) |
| **Linear** | `P1-M2-T1` schema · `P1-M2-T2` product API · `P1-M2-T3` stock API · `P1-M2-T4` product grid UI |

### Module P1-M3 — POS Cart & Checkout

| Field | Chi tiết |
|-------|----------|
| **Goal** | Draft cart → discount → finalize → payment → trừ stock atomic |
| **Schema** | `orders`, `order_lines`, `payments`; status: `draft|held|paid|void|refunded` |
| **API** | `POST /orders`, `POST /orders/{id}/lines`, `PATCH /orders/{id}`, `POST /orders/{id}/pay`, `POST /orders/{id}/void` |
| **Frontend** | Cart sidebar, qty +/-, % discount, note, hold/resume |
| **Rules** | Transaction: create payment + set paid + decrement stock **1 DB transaction**; idempotency-key header |
| **Offline** | Local draft queue (IndexedDB) → sync `POST /orders/sync` |
| **Tests** | concurrent pay; stock race; partial payment (phase1: 1 payment only) |
| **Linear** | `P1-M3-T1` order schema · `P1-M3-T2` cart API · `P1-M3-T3` pay atomic · `P1-M3-T4` cart UI · `P1-M3-T5` offline queue stub |

### Module P1-M4 — Customer CRM Core

| Field | Chi tiết |
|-------|----------|
| **Goal** | Tìm/thêm KH theo SĐT; gán vào order; lịch sử mua |
| **Schema** | `customers` (phone unique, name, email, tags jsonb, notes), `customer_addresses` |
| **API** | `GET /customers/search`, `POST /customers`, `PATCH /customers/{id}`, `GET /customers/{id}/orders` |
| **Frontend** | Modal tìm/thêm KH trên POS; tab lịch sử |
| **Rules** | Auto-create by phone nếu chưa có khi checkout; normalize phone VN (+84) |
| **Tests** | search phone; attach customer to order |
| **Linear** | `P1-M4-T1` schema · `P1-M4-T2` customer API · `P1-M4-T3` POS modal · `P1-M4-T4` history tab |

### Module P1-M5 — Receipt & Daily report

| Field | Chi tiết |
|-------|----------|
| **Goal** | In/PDF bill; tổng kết cuối ngày theo store |
| **Schema** | (dùng orders) + optional `receipts` log |
| **API** | `GET /orders/{id}/receipt`, `GET /reports/daily-sales?store_id=&date=` |
| **Frontend** | Print preview; end-of-day screen |
| **Rules** | ESC-POS template text; PDF fallback |
| **Linear** | `P1-M5-T1` receipt template · `P1-M5-T2` daily sales API · `P1-M5-T3` EOD UI |

### Phase 1 exit criteria

- [ ] Cashier login → chọn store → scan/add SP → gán KH → pay → stock giảm  
- [ ] Manager xem daily sales  
- [ ] 1 store demo data seed  

---

## Phase 2 – Loyalty + Inventory nâng cao (3–4 tuần)

**Epic:** `P2 – Loyalty & Advanced Inventory`

### P2-M1 Loyalty & Points

- Schema: `loyalty_programs`, `customer_points`, `point_transactions`, `rewards`  
- Rules: earn % of subtotal; redeem at checkout; expiry job  
- API: balance, preview earn/redeem, apply on pay  
- UI: điểm trên cart + gợi ý reward  
- Linear: `P2-M1-T1` … `P2-M1-T4`

### P2-M2 Inventory nâng cao

- Transfer inter-store, stocktake, low-stock alert, optional batch/lot  
- Event: `stock.updated`  
- Linear: `P2-M2-T1` transfer · `P2-M2-T2` stocktake · `P2-M2-T3` alerts

### P2-M3 Promotion engine

- Schema: `promotions` (percent, fixed, BXGY, coupon)  
- Rule eval order: coupon → BXGY → % cart  
- Linear: `P2-M3-T1` schema · `P2-M3-T2` engine · `P2-M3-T3` apply on cart

### Phase 2 exit

- [ ] Mua hàng tích điểm + redeem  
- [ ] Transfer stock 2 cửa hàng  
- [ ] 1 promotion % + 1 coupon  

---

## Phase 3 – Omnichannel + Analytics + AI (4–6 tuần)

**Epic:** `P3 – Events, Analytics, AI`

### P3-M1 Event bus

- Outbox pattern: `outbox_events` table  
- Workers: Celery/Redis consume `order.created`, `customer.updated`, `points.earned`  
- Linear: `P3-M1-T1` outbox · `P3-M1-T2` workers · `P3-M1-T3` retries

### P3-M2 Advanced CRM

- RFM segments, customer timeline, follow-up tasks  
- Linear: `P3-M2-T1` RFM job · `P3-M2-T2` timeline API · `P3-M2-T3` tasks UI

### P3-M3 Analytics dashboard

- Revenue by hour/day/store, top products, CLV  
- Materialized views or daily aggregates  
- Linear: `P3-M3-T1` aggregates · `P3-M3-T2` dashboard API · `P3-M3-T3` charts UI

### P3-M4 AI at POS

- Recommend products (co-purchase + history)  
- Next-best-action cho cashier (dùng LangGraph + Mem0)  
- Optional churn score batch  
- Linear: `P3-M4-T1` feature extract · `P3-M4-T2` recommend API · `P3-M4-T3` POS coach panel · `P3-M4-T4` wire existing agents

### P3-M5 Integrations VN

- VNPay/MoMo/ZaloPay sandbox  
- E-invoice stub  
- SMS/Zalo notify  
- Linear: `P3-M5-T1` payment adapter · `P3-M5-T2` e-invoice stub · `P3-M5-T3` notify

---

## Phase 4 – Production ready (3–4 tuần)

**Epic:** `P4 – Production`

| Module | Tasks |
|--------|-------|
| P4-M1 Offline-first | Conflict resolution, vector clocks / last-write + manual resolve |
| P4-M2 i18n | VI/EN |
| P4-M3 Security | Audit log, secrets, rate limit, PCI scope (token only) |
| P4-M4 Ops | Sentry, metrics, backup, CI/CD, seed/staging |
| P4-M5 SoftPOS mode | PWA install, camera barcode, large touch targets |
| P4-M6 Reports export | Excel/PDF RBAC |

---

## Thứ tự code khuyến nghị (sprint-sized)

```text
Sprint 1: P1-M1 Auth + P1-M2 Catalog (API first)
Sprint 2: P1-M3 Cart/Pay atomic + seed demo
Sprint 3: P1-M4 Customer + P1-M5 Receipt/Report + POS UI shell
Sprint 4: Harden MVP + offline stub
Sprint 5–6: P2 Loyalty + Promos + Transfer
Sprint 7–8: P3 Events + Analytics + AI recommend
Sprint 9: P4 SoftPOS + ops
```

---

## Mapping Linear → pipeline agents

| Khi issue created | Agent làm gì |
|-------------------|--------------|
| Title có `[P1-M3]` | Ava: plan schema order/payment atomic |
| | Rex: code FastAPI + tests |
| | Kai: review race stock / money |
| Label `type:feature` | Full pipeline |
| Label `type:chore` | Có thể skip heavy review sau |

**Convention title** giúp Mem0 + agents nhận module:

```text
[P1-M3-T3] Atomic pay: decrement stock + create payment
```

---

## Rủi ro & mitigation

| Risk | Mitigation |
|------|------------|
| Stock race | `SELECT FOR UPDATE` / version column |
| Double pay | Idempotency-Key |
| Offline conflict | Server wins money; client re-fetch catalog |
| Scope creep VN e-invoice | Stub phase 3, full phase 4+ |
| AI without data | Rule-based recommend trước ML |

---

*Backlog copy-paste Linear: `docs/linear/LINEAR_BACKLOG.md`*  
*Script tạo issue (khi có API key): `docs/linear/push_linear_issues.py`*
