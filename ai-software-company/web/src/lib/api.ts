const API_BASE = import.meta.env.VITE_API_BASE ?? ''

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

  const res = await fetch(`${API_BASE}${path}`, {
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
}

export function money(v: string | number | undefined) {
  const n = Number(v ?? 0)
  return n.toLocaleString('vi-VN') + '₫'
}
