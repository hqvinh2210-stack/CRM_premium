/**
 * API origin for SoftPOS.
 * Default: same-origin (empty) — open UI at http://127.0.0.1:8001 so only email/password.
 * Optional override: VITE_API_BASE at build, or localStorage.pos_api_base.
 */
function resolveApiBase(): string {
  try {
    const saved = localStorage.getItem('pos_api_base')
    if (saved) return saved.replace(/\/$/, '')
  } catch {
    /* ignore */
  }
  const env = (import.meta.env.VITE_API_BASE as string | undefined)?.trim()
  if (env) return env.replace(/\/$/, '')
  // Same host as the page (Docker SPA at :8001) — no API URL needed
  return ''
}

export function getApiBase() {
  return resolveApiBase()
}

export function setApiBase(url: string) {
  const cleaned = url.trim().replace(/\/$/, '')
  if (cleaned) localStorage.setItem('pos_api_base', cleaned)
  else localStorage.removeItem('pos_api_base')
}

/** Clear wrong API override so login uses same-origin again. */
export function clearApiBase() {
  try {
    localStorage.removeItem('pos_api_base')
  } catch {
    /* ignore */
  }
}

export type Product = {
  id: string
  sku: string
  name: string
  price: string | number
  barcode?: string | null
  stock_qty?: number | null
  track_inventory?: boolean
}

export type OrderLine = {
  id: string
  product_id: string
  product_name: string
  qty: number
  unit_price: string | number
  line_discount: string | number
  line_total: string | number
}

export type Order = {
  id: string
  status: string
  subtotal: string | number
  discount: string | number
  total: string | number
  discount_percent: string | number
  customer_id?: string | null
  note?: string | null
  lines: OrderLine[]
  payments?: { method: string; amount: string | number }[]
}

export type Customer = {
  id: string
  phone: string
  name: string
  email?: string | null
  tags?: string | null
  notes?: string | null
  created_at?: string | null
}

export type CustomerProfile = {
  customer: Customer
  points: { balance: number; lifetime_earned: number }
  stats: {
    order_count: number
    total_spend: string
    last_purchase: string | null
    recency_days: number | null
    segment: string
  }
  orders: {
    id: string
    total: string
    status: string
    paid_at: string | null
    lines: { product_name: string; qty: number; line_total: string }[]
  }[]
}

type HeadersInit_ = Record<string, string>

async function request<T>(
  path: string,
  options: RequestInit & { token?: string; storeId?: string } = {},
): Promise<T> {
  const headers: HeadersInit_ = {
    'Content-Type': 'application/json',
    ...(options.headers as HeadersInit_),
  }
  if (options.token) headers.Authorization = `Bearer ${options.token}`
  if (options.storeId) headers['X-Store-Id'] = options.storeId

  const base = resolveApiBase()
  const res = await fetch(`${base}${path}`, {
    ...options,
    headers,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail
        ? typeof body.detail === 'string'
          ? body.detail
          : JSON.stringify(body.detail)
        : detail
    } catch {
      /* ignore */
    }
    throw new Error(detail || `HTTP ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  login(email: string, password: string, storeId?: string) {
    return request<{
      access_token: string
      refresh_token: string
      store_id: string
      role: string
    }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password, store_id: storeId ?? null }),
    })
  },
  me(token: string) {
    return request<{
      user: { id: string; email: string; full_name: string }
      stores: { store_id: string; code: string; name: string; role: string }[]
    }>('/api/v1/auth/me', { token })
  },
  products(token: string, storeId: string, q?: string) {
    const qs = q ? `?q=${encodeURIComponent(q)}` : ''
    return request<Product[]>(`/api/v1/products${qs}`, { token, storeId })
  },
  productByBarcode(token: string, storeId: string, code: string) {
    return request<Product>(`/api/v1/products/barcode/${encodeURIComponent(code)}`, {
      token,
      storeId,
    })
  },
  createOrder(token: string, storeId: string, customerId?: string) {
    return request<Order>('/api/v1/orders', {
      method: 'POST',
      token,
      storeId,
      body: JSON.stringify({ customer_id: customerId ?? null }),
    })
  },
  addLine(token: string, storeId: string, orderId: string, productId: string, qty = 1) {
    return request<Order>(`/api/v1/orders/${orderId}/lines`, {
      method: 'POST',
      token,
      storeId,
      body: JSON.stringify({ product_id: productId, qty }),
    })
  },
  updateLine(
    token: string,
    storeId: string,
    orderId: string,
    lineId: string,
    qty: number,
  ) {
    return request<Order>(`/api/v1/orders/${orderId}/lines/${lineId}`, {
      method: 'PATCH',
      token,
      storeId,
      body: JSON.stringify({ qty }),
    })
  },
  deleteLine(token: string, storeId: string, orderId: string, lineId: string) {
    return request<Order>(`/api/v1/orders/${orderId}/lines/${lineId}`, {
      method: 'DELETE',
      token,
      storeId,
    })
  },
  updateOrder(
    token: string,
    storeId: string,
    orderId: string,
    body: { customer_id?: string | null; discount_percent?: number; note?: string },
  ) {
    return request<Order>(`/api/v1/orders/${orderId}`, {
      method: 'PATCH',
      token,
      storeId,
      body: JSON.stringify(body),
    })
  },
  pay(
    token: string,
    storeId: string,
    orderId: string,
    idempotencyKey: string,
    extra?: { promo_code?: string; redeem_points?: number },
  ) {
    return request<Order>(`/api/v1/orders/${orderId}/pay`, {
      method: 'POST',
      token,
      storeId,
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({
        method: 'cash',
        promo_code: extra?.promo_code ?? null,
        redeem_points: extra?.redeem_points ?? 0,
      }),
    })
  },
  receipt(token: string, storeId: string, orderId: string) {
    return request<{ text: string; order_id: string }>(
      `/api/v1/orders/${orderId}/receipt`,
      { token, storeId },
    )
  },
  listCustomers(token: string, storeId: string, q?: string) {
    const qs = q?.trim() ? `?q=${encodeURIComponent(q.trim())}` : ''
    return request<Customer[]>(`/api/v1/customers${qs}`, { token, storeId })
  },
  searchCustomers(token: string, storeId: string, q: string) {
    return request<Customer[]>(
      `/api/v1/customers/search?q=${encodeURIComponent(q)}`,
      { token, storeId },
    )
  },
  createCustomer(token: string, storeId: string, phone: string, name: string) {
    return request<Customer>('/api/v1/customers', {
      method: 'POST',
      token,
      storeId,
      body: JSON.stringify({ phone, name }),
    })
  },
  updateCustomer(
    token: string,
    storeId: string,
    id: string,
    body: { name?: string; notes?: string; email?: string; tags?: string },
  ) {
    return request<Customer>(`/api/v1/customers/${id}`, {
      method: 'PATCH',
      token,
      storeId,
      body: JSON.stringify(body),
    })
  },
  customerProfile(token: string, storeId: string, id: string) {
    return request<CustomerProfile>(`/api/v1/customers/${id}/profile`, {
      token,
      storeId,
    })
  },
  customerOrders(token: string, storeId: string, id: string) {
    return request<Order[]>(`/api/v1/customers/${id}/orders`, { token, storeId })
  },
  rfm(token: string, storeId: string) {
    return request<{
      segments: {
        customer_id: string
        name: string
        phone: string
        segment: string
        frequency: number
        monetary: string
        recency_days: number
      }[]
      count: number
    }>('/api/v1/reports/rfm', { token, storeId })
  },

  dailySales(token: string, storeId: string) {
    return request<{
      date: string
      order_count: number
      gross: string
      net: string
      discount: string
      by_payment_method: Record<string, string>
      top_products: { name: string; qty: number; revenue: string }[]
    }>('/api/v1/reports/daily-sales', { token, storeId })
  },
  syncOffline(
    token: string,
    storeId: string,
    orders: unknown[],
  ) {
    return request<{
      ok: boolean
      results: { client_id: string; ok: boolean; error?: string; order_id?: string }[]
    }>('/api/v1/orders/sync', {
      method: 'POST',
      token,
      storeId,
      body: JSON.stringify({ orders }),
    })
  },
  recommend(token: string, storeId: string, productIds: string[], customerId?: string) {
    const q = new URLSearchParams()
    if (productIds.length) q.set('product_ids', productIds.join(','))
    if (customerId) q.set('customer_id', customerId)
    return request<{ items: { name: string; price: string; reason: string }[]; next_best_action?: string }>(
      `/api/v1/ai/recommend?${q}`,
      { token, storeId },
    )
  },
  loyaltyPoints(token: string, storeId: string, customerId: string) {
    return request<{ balance: number; redeemable_vnd: number }>(
      `/api/v1/loyalty/points/${customerId}`,
      { token, storeId },
    )
  },
  applyPromo(token: string, storeId: string, orderId: string, code?: string) {
    return request<{ total: string; promo_name?: string }>(
      `/api/v1/promotions/orders/${orderId}/apply`,
      { method: 'POST', token, storeId, body: JSON.stringify({ code: code ?? null }) },
    )
  },
  refund(token: string, storeId: string, orderId: string, reason?: string) {
    return request<Order>(`/api/v1/orders/${orderId}/refund`, {
      method: 'POST',
      token,
      storeId,
      body: JSON.stringify({ reason: reason ?? null }),
    })
  },
  lowStock(token: string, storeId: string, threshold = 10) {
    return request<{ threshold: number; items: { product_id: string; sku: string; name: string; qty: number }[] }>(
      `/api/v1/inventory/low-stock?threshold=${threshold}`,
      { token, storeId },
    )
  },
  transferStock(
    token: string,
    storeId: string,
    body: { from_store_id: string; to_store_id: string; product_id: string; qty: number; note?: string },
  ) {
    return request<{ id: string; status: string; qty: number; to_store_id: string }>(
      '/api/v1/inventory/transfers',
      { method: 'POST', token, storeId, body: JSON.stringify(body) },
    )
  },
  stocktake(
    token: string,
    storeId: string,
    body: { product_id: string; counted_qty: number; note?: string; apply_adjustment?: boolean },
  ) {
    return request<{
      id: string
      system_qty: number
      counted_qty: number
      variance: number
      applied: boolean
    }>('/api/v1/inventory/stocktake', {
      method: 'POST',
      token,
      storeId,
      body: JSON.stringify(body),
    })
  },
  customerTimeline(token: string, storeId: string, customerId: string) {
    return request<{
      customer_id: string
      count: number
      events: {
        at: string | null
        kind: string
        title: string
        ref_id: string
        meta?: Record<string, unknown>
      }[]
    }>(`/api/v1/customers/${customerId}/timeline`, { token, storeId })
  },
  analytics(token: string, storeId: string, days = 7) {
    return request<{
      days: number
      totals: {
        order_count: number
        revenue: string
        customers: number
        avg_order_value: string
        clv_proxy_avg: string
      }
      by_day: { date: string; order_count: number; revenue: string }[]
      by_hour_today: { hour: number; revenue: string }[]
      top_products: { name: string; qty: number; revenue: string }[]
    }>(`/api/v1/reports/analytics?days=${days}`, { token, storeId })
  },
  listTasks(token: string, storeId: string, customerId?: string, status = 'open') {
    const q = new URLSearchParams({ status })
    if (customerId) q.set('customer_id', customerId)
    return request<{
      tasks: {
        id: string
        customer_id: string
        title: string
        notes?: string | null
        status: string
        due_at?: string | null
      }[]
    }>(`/api/v1/tasks?${q}`, { token, storeId })
  },
  createTask(
    token: string,
    storeId: string,
    body: { customer_id: string; title: string; notes?: string },
  ) {
    return request<{ id: string; title: string; status: string }>('/api/v1/tasks', {
      method: 'POST',
      token,
      storeId,
      body: JSON.stringify(body),
    })
  },
  updateTask(
    token: string,
    storeId: string,
    id: string,
    body: { status?: string; title?: string; notes?: string },
  ) {
    return request<{ id: string; status: string }>(`/api/v1/tasks/${id}`, {
      method: 'PATCH',
      token,
      storeId,
      body: JSON.stringify(body),
    })
  },
  issueEinvoice(
    token: string,
    storeId: string,
    orderId: string,
    extra?: { tax_code?: string; buyer_name?: string },
  ) {
    return request<{ id: string; invoice_no: string; status: string }>(
      '/api/v1/invoices/e-invoice',
      {
        method: 'POST',
        token,
        storeId,
        body: JSON.stringify({ order_id: orderId, ...extra }),
      },
    )
  },
  notifyOrder(token: string, storeId: string, orderId: string, phone?: string) {
    return request<{ id: string; status: string; channel: string }>('/api/v1/notify/order', {
      method: 'POST',
      token,
      storeId,
      body: JSON.stringify({ order_id: orderId, phone: phone ?? null, channel: 'sms' }),
    })
  },
  exportCsvUrl(days = 7) {
    return `${resolveApiBase()}/api/v1/reports/export.csv?days=${days}`
  },
  exportPdfUrl(date?: string) {
    const q = date ? `?date=${date}` : ''
    return `${resolveApiBase()}/api/v1/reports/export.pdf${q}`
  },
  exportXlsxUrl(days = 7) {
    return `${resolveApiBase()}/api/v1/reports/export.xlsx?days=${days}`
  },
  opsMetrics(token: string, storeId: string) {
    return request<{
      orders_today: number
      revenue_today: string
      cash_sales_today: string
      customers_total: number
      low_stock_skus: number
      outbox: { pending_or_failed: number; dead_letter: number }
      shift: {
        id: string
        status: string
        opening_cash: string
        opened_at?: string | null
        user_id: string
      } | null
    }>('/api/v1/ops/metrics', { token, storeId })
  },
  opsAudit(token: string, storeId: string, limit = 50) {
    return request<{
      count: number
      items: {
        action: string
        detail?: string | null
        created_at?: string | null
        entity?: string | null
        entity_id?: string | null
      }[]
    }>(`/api/v1/ops/audit?limit=${limit}`, { token, storeId })
  },
  opsStaff(token: string, storeId: string) {
    return request<{
      staff: {
        email: string
        full_name?: string | null
        role: string
        is_active: boolean
        user_id: string
      }[]
    }>('/api/v1/ops/staff', { token, storeId })
  },
  opsBackupUrl() {
    return `${resolveApiBase()}/api/v1/ops/backup.json`
  },
  openShift(token: string, storeId: string, opening_cash = 0, note?: string) {
    return request<{ id: string; status: string; opening_cash: string }>(
      '/api/v1/shifts/open',
      {
        method: 'POST',
        token,
        storeId,
        body: JSON.stringify({ opening_cash, note: note ?? null }),
      },
    )
  },
  closeShift(
    token: string,
    storeId: string,
    shiftId: string,
    closing_cash: number,
    note?: string,
  ) {
    return request<{
      id: string
      status: string
      variance?: string | null
      expected_cash?: string | null
    }>(`/api/v1/shifts/${shiftId}/close`, {
      method: 'POST',
      token,
      storeId,
      body: JSON.stringify({ closing_cash, note: note ?? null }),
    })
  },
  currentShift(token: string, storeId: string) {
    return request<{ shift: { id: string; status: string; opening_cash: string } | null }>(
      '/api/v1/shifts/current',
      { token, storeId },
    )
  },

  posAgentEvent(
    token: string,
    storeId: string,
    event_type: string,
    payload: Record<string, unknown>,
    sync = false,
  ) {
    return request<{ ok?: boolean; queued?: boolean; status?: string; skipped?: boolean }>(
      '/api/v1/ai/event',
      {
        method: 'POST',
        token,
        storeId,
        body: JSON.stringify({ event_type, payload, sync }),
      },
    )
  },
}

export function money(v: string | number | undefined) {
  const n = Number(v ?? 0)
  return n.toLocaleString('vi-VN') + '₫'
}
