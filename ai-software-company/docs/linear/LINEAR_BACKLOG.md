# Linear Backlog — POS + CRM (CRM_premium)

Import bằng tay (copy issue) **hoặc** chạy:

```powershell
cd C:\Users\admin\Downloads\CRM\ai-software-company
# set LINEAR_API_KEY + LINEAR_TEAM_ID in .env
uv run python docs/linear/push_linear_issues.py --phase 1
```

Mỗi issue create → webhook → orchestrator → LangGraph (Ava → Rex → Kai) nếu pipeline đang chạy.

---

## Epics (tạo trước, parent)

| Identifier suggestion | Title | Description |
|----------------------|-------|-------------|
| EPIC-P1 | [Epic] P1 – MVP Core POS + CRM | Auth, catalog, cart/pay, customer, receipt |
| EPIC-P2 | [Epic] P2 – Loyalty & Advanced Inventory | Points, transfer, promos |
| EPIC-P3 | [Epic] P3 – Events, Analytics, AI | Outbox, RFM, dashboards, recommend, VN pay |
| EPIC-P4 | [Epic] P4 – Production Ready | Offline, i18n, audit, SoftPOS, CI/CD |

---

## Phase 1 issues (tạo theo thứ tự)

### Auth

#### P1-M1-T1
**Title:** `[P1-M1-T1] DB schema: users, stores, user_store_roles, refresh_tokens`

```markdown
## Goal
Tạo foundation multi-store + multi-user cho POS.

## Acceptance criteria
- [ ] Migration Alembic/SQLAlchemy tạo bảng users, stores, user_store_roles, refresh_tokens
- [ ] Enum role: cashier | manager | admin
- [ ] Seed 1 admin + 1 store demo

## Schema
- users: id, email, phone, password_hash, is_active, created_at
- stores: id, code, name, address, timezone, is_active
- user_store_roles: user_id, store_id, role (unique user+store)
- refresh_tokens: id, user_id, token_hash, expires_at, revoked

## API
(none this task)

## Tests
- [ ] migration up/down
- [ ] seed loads

## Agent handoff
Ava plan tables; Rex implement models+migration; Kai review indexes & unique constraints.
```

#### P1-M1-T2
**Title:** `[P1-M1-T2] Auth API: login, refresh, me`

```markdown
## Goal
JWT access + refresh login flow.

## Acceptance criteria
- [ ] POST /auth/login {email|phone, password, store_id?} → access + refresh
- [ ] POST /auth/refresh
- [ ] GET /auth/me
- [ ] Password hashed (bcrypt/argon2)

## Business rules
- Access TTL 15m, refresh 7d
- Login fail generic message

## Tests
- [ ] happy path
- [ ] wrong password 401
```

#### P1-M1-T3
**Title:** `[P1-M1-T3] RBAC middleware require_role + store scope`

```markdown
## Goal
Mọi API POS enforce role + store_id.

## Acceptance criteria
- [ ] Dependency require_roles("cashier","manager","admin")
- [ ] Header/context X-Store-Id validated against membership
- [ ] 403 when wrong store

## Tests
- [ ] cashier denied admin route
- [ ] cross-store blocked
```

#### P1-M1-T4
**Title:** `[P1-M1-T4] Frontend: Login + Store selector`

```markdown
## Goal
UI đăng nhập và chọn cửa hàng (touch-friendly).

## Acceptance criteria
- [ ] Login form
- [ ] Store list sau login
- [ ] Persist tokens (memory + secure storage)
- [ ] Redirect vào POS shell

## Frontend
LoginPage, StoreSelector, auth store (Zustand)
```

---

### Catalog

#### P1-M2-T1
**Title:** `[P1-M2-T1] DB schema: categories, products, stock_levels`

```markdown
## Goal
Catalog + tồn theo cửa hàng.

## Acceptance criteria
- [ ] products: sku, name, price, cost, barcode, category_id, track_inventory, deleted_at
- [ ] stock_levels: store_id, product_id, qty, version
- [ ] Unique barcode (nullable), unique sku

## Tests
- [ ] constraints
```

#### P1-M2-T2
**Title:** `[P1-M2-T2] Product CRUD + search + barcode lookup API`

```markdown
## Goal
API quản lý & tìm sản phẩm cho POS grid.

## API
- CRUD /products
- GET /products/search?q=
- GET /products/barcode/{code}

## Acceptance criteria
- [ ] Soft-delete
- [ ] Search name/sku/barcode
- [ ] Pagination
```

#### P1-M2-T3
**Title:** `[P1-M2-T3] Stock adjust API with reason`

```markdown
## Goal
Điều chỉnh tồn có audit reason.

## API
POST /stock/adjust {product_id, store_id, delta, reason}

## Business rules
- Optional block negative if track_inventory
- version optimistic lock
```

#### P1-M2-T4
**Title:** `[P1-M2-T4] Frontend Product grid + barcode input`

```markdown
## Goal
Màn hình chọn hàng touch POS.

## Acceptance criteria
- [ ] Grid/cards large touch targets
- [ ] Search + barcode field (Enter to add)
- [ ] Low-stock badge when qty low
```

---

### Orders / Cart

#### P1-M3-T1
**Title:** `[P1-M3-T1] DB schema: orders, order_lines, payments`

```markdown
## Goal
Transaction model cho POS.

## Schema
- orders: store_id, user_id, customer_id, status, subtotal, discount, tax, total, note, paid_at
- order_lines: order_id, product_id, qty, unit_price, line_discount, line_total
- payments: order_id, method (cash|card|ewallet), amount, ref, created_at
- status: draft|held|paid|void|refunded

## Tests
- [ ] FKs + check total >= 0
```

#### P1-M3-T2
**Title:** `[P1-M3-T2] Cart API: create draft, add/update lines, hold`

```markdown
## Goal
Xây giỏ hàng server-side.

## API
POST /orders
POST /orders/{id}/lines
PATCH /orders/{id}/lines/{line_id}
POST /orders/{id}/hold
POST /orders/{id}/resume

## Rules
- Only draft/held editable
- Recalc totals server-side
```

#### P1-M3-T3
**Title:** `[P1-M3-T3] Atomic pay: payment + stock decrement + paid status`

```markdown
## Goal
Thanh toán an toàn tiền + tồn.

## API
POST /orders/{id}/pay
Headers: Idempotency-Key

## Business rules
- Single DB transaction
- Decrement stock_levels for track_inventory products
- Idempotent replay same key returns same order
- Reject pay if already paid

## Tests
- [ ] concurrent double-pay blocked
- [ ] stock race
- [ ] idempotency
```

#### P1-M3-T4
**Title:** `[P1-M3-T4] Frontend Cart sidebar + checkout`

```markdown
## Goal
UI giỏ: qty, discount %, note, pay cash.

## Acceptance criteria
- [ ] Add from grid
- [ ] +/- qty
- [ ] Discount %
- [ ] Pay button → success receipt state
```

#### P1-M3-T5
**Title:** `[P1-M3-T5] Offline queue stub (IndexedDB → sync)`

```markdown
## Goal
Lưu draft offline, sync khi online (MVP stub).

## Acceptance criteria
- [ ] Save cart local when offline flag
- [ ] POST /orders/sync batch
- [ ] Basic conflict: fail line if product missing
```

---

### Customer CRM

#### P1-M4-T1
**Title:** `[P1-M4-T1] DB schema: customers, customer_addresses`

```markdown
## Goal
CRM core identity.

## Schema
customers: phone unique, name, email, tags jsonb, notes, created_at
customer_addresses: customer_id, line, city, is_default
```

#### P1-M4-T2
**Title:** `[P1-M4-T2] Customer search/create/update + order history API`

```markdown
## API
GET /customers/search?q=
POST /customers
PATCH /customers/{id}
GET /customers/{id}/orders

## Rules
- Normalize VN phone
- Auto-create on checkout optional flag
```

#### P1-M4-T3
**Title:** `[P1-M4-T3] POS modal find/add customer`

```markdown
## Goal
Gắn khách vào order ngay trên POS.

## Acceptance criteria
- [ ] Search by phone
- [ ] Create if not found
- [ ] Attach to current cart
```

#### P1-M4-T4
**Title:** `[P1-M4-T4] Customer purchase history tab`

```markdown
## Goal
Xem 10 order gần nhất của KH.

## Acceptance criteria
- [ ] List date, total, items count
- [ ] Open order detail read-only
```

---

### Receipt / Report

#### P1-M5-T1
**Title:** `[P1-M5-T1] Receipt template text/PDF`

```markdown
## Goal
GET /orders/{id}/receipt → text ESC-POS friendly + PDF optional
```

#### P1-M5-T2
**Title:** `[P1-M5-T2] Daily sales report API`

```markdown
## API
GET /reports/daily-sales?store_id=&date=
## Returns
gross, net, order_count, by_payment_method, top_products
```

#### P1-M5-T3
**Title:** `[P1-M5-T3] End-of-day summary UI`

```markdown
## Goal
Màn hình manager xem EOD + print
```

---

## Phase 2 (rút gọn title list)

| ID | Title |
|----|-------|
| P2-M1-T1 | `[P2-M1-T1] Loyalty schema: programs, points, transactions, rewards` |
| P2-M1-T2 | `[P2-M1-T2] Earn/redeem points on checkout` |
| P2-M1-T3 | `[P2-M1-T3] POS UI points balance + redeem suggestion` |
| P2-M1-T4 | `[P2-M1-T4] Points expiry job` |
| P2-M2-T1 | `[P2-M2-T1] Inter-store stock transfer` |
| P2-M2-T2 | `[P2-M2-T2] Stocktake session + variance` |
| P2-M2-T3 | `[P2-M2-T3] Low-stock alerts` |
| P2-M3-T1 | `[P2-M3-T1] Promotions schema` |
| P2-M3-T2 | `[P2-M3-T2] Promotion rule engine` |
| P2-M3-T3 | `[P2-M3-T3] Apply promo on cart UI` |

## Phase 3 titles

| ID | Title |
|----|-------|
| P3-M1-T1 | `[P3-M1-T1] Outbox events table + publisher` |
| P3-M1-T2 | `[P3-M1-T2] Celery/Redis workers order.created` |
| P3-M1-T3 | `[P3-M1-T3] Retry + dead-letter` |
| P3-M2-T1 | `[P3-M2-T1] RFM segmentation job` |
| P3-M2-T2 | `[P3-M2-T2] Customer timeline API` |
| P3-M2-T3 | `[P3-M2-T3] Follow-up tasks CRM UI` |
| P3-M3-T1 | `[P3-M3-T1] Sales aggregate tables/views` |
| P3-M3-T2 | `[P3-M3-T2] Analytics dashboard API` |
| P3-M3-T3 | `[P3-M3-T3] Charts dashboard UI` |
| P3-M4-T1 | `[P3-M4-T1] Co-purchase feature extract` |
| P3-M4-T2 | `[P3-M4-T2] Recommend products API` |
| P3-M4-T3 | `[P3-M4-T3] POS next-best-action coach panel` |
| P3-M4-T4 | `[P3-M4-T4] Wire LangGraph agents to POS events` |
| P3-M5-T1 | `[P3-M5-T1] VNPay/MoMo sandbox adapter` |
| P3-M5-T2 | `[P3-M5-T2] E-invoice stub` |
| P3-M5-T3 | `[P3-M5-T3] Zalo/SMS notify on order` |

## Phase 4 titles

| ID | Title |
|----|-------|
| P4-M1-T1 | `[P4-M1-T1] Offline conflict resolution` |
| P4-M2-T1 | `[P4-M2-T1] i18n VI/EN` |
| P4-M3-T1 | `[P4-M3-T1] Audit log + rate limit` |
| P4-M4-T1 | `[P4-M4-T1] Sentry + CI/CD pipeline` |
| P4-M5-T1 | `[P4-M5-T1] SoftPOS PWA mode` |
| P4-M6-T1 | `[P4-M6-T1] Export Excel/PDF reports` |

---

## Labels đề xuất trên Linear

```text
phase-1, phase-2, phase-3, phase-4
module:auth, module:catalog, module:orders, module:customers,
module:loyalty, module:inventory, module:promo, module:events,
module:analytics, module:ai, module:payments, module:ops
type:feature, type:chore, type:bug
area:backend, area:frontend
```

## Priority gợi ý Phase 1

| Task | Priority |
|------|----------|
| P1-M1-T1, T2, T3 | High |
| P1-M2-T1, T2 | High |
| P1-M3-T1, T2, T3 | Urgent |
| P1-M3-T4 | High |
| P1-M4-* | High |
| P1-M5-* | Medium |
| P1-M3-T5 offline | Medium |
