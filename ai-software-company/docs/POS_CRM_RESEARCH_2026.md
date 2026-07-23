# POS + CRM: Tài liệu & xu hướng công nghệ (2025–2026)

Tài liệu tham chiếu để định hướng product **CRM_premium / AI Software Company POS**.  
Cập nhật: 2026-07.

---

## 1. Tóm tắt executive

| Xu hướng | Ý nghĩa cho product | Ưu tiên build |
|----------|---------------------|---------------|
| **Unified Commerce** | 1 DB cho in-store + online + mobile; không silo POS/CRM | Single PostgreSQL domain model |
| **Cloud POS** | ~79% vendor có cloud hosting | FastAPI cloud-first API |
| **SoftPOS** | Vendor SoftPOS 16% → **24%** (1 năm) | PWA / tablet-first UI |
| **AI-native** | POS → CRM next-best-action, coaching, upsell | LangGraph agents + memory (đã có) |
| **API-first + events** | Webhook, queue, real-time sync | Outbox + Redis/Celery |
| **Offline-first** | Cửa hàng mất mạng vẫn bán | IndexedDB + sync queue |
| **Loyalty + Clienteling** | Profile 360° trên màn hình POS | Customer + points trên cart |
| **Open-source stack** | Odoo / ERPNext làm reference architecture | Python monorepo modules |

---

## 2. Nguồn & số liệu chính

### 2.1 Unified Commerce + SoftPOS + Cloud

- **Digital Transactions / industry directory (2026):**
  - Unified Commerce: **24%** vendor định vị “Unified Commerce”; **35%** omnichannel; **17%** cả hai.
  - SoftPOS: **16% → 24%** trong một năm.
  - Cloud: **79%** có ít nhất 1 product cloud; chỉ **~3%** còn market on-prem thuần.
  - Nguồn: [Yahoo Finance / Digital Transactions coverage](https://finance.yahoo.com/small-business/articles/unified-commerce-becomes-pos-battleground-130500777.html)

### 2.2 SoftPOS growth (thị trường)

- Juniper Research: Soft POS transaction value toàn cầu **$23.9B (2025) → $540B (2030)** (~2150% tăng).  
  - [Juniper press](https://www.juniperresearch.com/press/soft-pos-transactions-to-accelerate-by-2150/)

### 2.3 Cloud POS market

- Mordor: Cloud POS ~**$6.26B (2025) → $7.32B (2026)**, CAGR ~17% tới 2031.  
  - [Mordor Intelligence](https://www.mordorintelligence.com/industry-reports/cloud-point-of-sale-market)

### 2.4 Platform vendors (tham chiếu product)

| Vendor | Góc nhìn áp dụng |
|--------|------------------|
| [Salesforce POS / Commerce](https://www.salesforce.com/commerce/point-of-sale/) | Mobile-first, clienteling, unified B2C + POS + OMS, API-first, Agentforce AI |
| Microsoft Dynamics 365 Commerce | Enterprise unified, inventory + store ops |
| Odoo POS + CRM | **1 DB** Python: bán hàng + CRM + inventory + accounting — ideal open-source reference |
| Openbravo / Orisha | POS là “brain” của unified commerce + agentic AI |
| ERPNext (Frappe) | Full ERP Python, multi-company |

### 2.5 Tích hợp phổ biến

1. **Native module** (cùng platform) — Odoo-style  
2. **REST/GraphQL API** — nhanh, kiểm soát cao  
3. **Middleware** (Zapier / queue / custom bus) — nhiều hệ thống  

Best practice 2026 (Odoo integration guides): rõ **system of record**, validation trước sync, retry + log, version API, security token/RBAC.

---

## 3. Pattern kiến trúc nên follow

```text
                    ┌─────────────────────┐
                    │  SoftPOS / PWA POS  │
                    │  Offline queue      │
                    └──────────┬──────────┘
                               │ HTTPS / JWT
                    ┌──────────▼──────────┐
                    │  FastAPI Gateway    │
                    └──┬────┬────┬────┬───┘
           Auth/Catalog│    │Orders│ CRM │ Loyalty │ Pay │ AI
                       └────┴────┴────┴───┘
                               │
              PostgreSQL (source of truth) + Redis (cache/events)
                               │
                    Event bus (outbox → workers)
                               │
              CRM analytics · Loyalty · Linear agents (build pipeline)
```

**Nguyên tắc:**

1. **One customer ID** xuyên POS / online / loyalty  
2. **Order là event trung tâm** (`order.created` → stock, points, CRM timeline)  
3. **Offline-first POS** — eventual consistency, idempotent sync  
4. **AI đọc cùng domain events** — không silo chat agent  

---

## 4. Mapping vào stack hiện tại (CRM_premium)

| Đã có | Dùng cho POS+CRM |
|-------|------------------|
| FastAPI + LangGraph | API gateway + AI recommendation / coding agents |
| Linear webhook → graph | Delivery pipeline: issue → plan → code → review |
| Mem0 + Gemini | Company memory: chuẩn stack, quyết định architecture |
| orchestrator + ngrok | Dev webhook ingress |

**Chưa có (cần build theo Linear tasks):** domain POS, PostgreSQL schema, POS frontend, payments VN.

---

## 5. Phạm vi MVP đề xuất (VN retail / F&B nhỏ)

- Multi-store, multi-cashier  
- Catalog + barcode + stock cơ bản  
- Cart → pay (tiền mặt + 1 gateway)  
- Customer 360° tối thiểu (phone key)  
- Daily sales report  
- (Stretch) Loyalty điểm cơ bản  

Không làm ngay: full e-invoice, Shopee sync, PCI raw card data, multi-country tax engine.

---

## 6. Tài liệu đọc thêm (bookmark)

- Salesforce Point of Sale: https://www.salesforce.com/commerce/point-of-sale/  
- Odoo integration architecture 2026: https://www.technaureus.com/blog-detail/odoo-integration-guide-2026  
- Unified commerce POS battleground: https://finance.yahoo.com/small-business/articles/unified-commerce-becomes-pos-battleground-130500777.html  
- Juniper Soft POS: https://www.juniperresearch.com/press/soft-pos-transactions-to-accelerate-by-2150/  
- Openbravo unified commerce AI: https://commerce.orisha.com/blog/openbravo-pos-unified-commerce-ai/  

---

*Document này là input cho plan implement + Linear backlog: xem `POS_CRM_IMPLEMENTATION_PLAN.md` và `linear/LINEAR_BACKLOG.md`.*
