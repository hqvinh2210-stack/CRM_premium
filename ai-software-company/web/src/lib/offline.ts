/** Offline order queue via IndexedDB (JIM-17). */

const DB_NAME = 'pos_offline_v1'
const STORE = 'pending_orders'

export type OfflineLine = {
  product_id: string
  qty: number
  unit_price?: number
  product_name?: string
}

export type OfflineOrder = {
  client_id: string
  customer_phone?: string | null
  customer_id?: string | null
  discount_percent: number
  note?: string | null
  lines: OfflineLine[]
  pay_method: 'cash' | 'card' | 'ewallet'
  created_at: string
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'client_id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export async function enqueueOfflineOrder(order: OfflineOrder): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).put(order)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
  db.close()
}

export async function listOfflineOrders(): Promise<OfflineOrder[]> {
  const db = await openDb()
  const rows = await new Promise<OfflineOrder[]>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly')
    const req = tx.objectStore(STORE).getAll()
    req.onsuccess = () => resolve(req.result as OfflineOrder[])
    req.onerror = () => reject(req.error)
  })
  db.close()
  return rows
}

export async function removeOfflineOrder(clientId: string): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).delete(clientId)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
  db.close()
}

export type SyncResultRow = {
  client_id: string
  ok: boolean
  error?: string
  order_id?: string
  status?: string
  resolution?: string | null
}

export type SyncResult = {
  ok: boolean
  results: SyncResultRow[]
  conflicts: SyncResultRow[]
  pending_left: number
}

export async function syncOfflineOrders(
  token: string,
  storeId: string,
): Promise<SyncResult> {
  const pending = await listOfflineOrders()
  if (!pending.length) return { ok: true, results: [], conflicts: [], pending_left: 0 }

  const res = await fetch('/api/v1/orders/sync', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      'X-Store-Id': storeId,
    },
    body: JSON.stringify({ orders: pending }),
  })
  if (!res.ok) {
    const t = await res.text()
    throw new Error(t || `Sync failed ${res.status}`)
  }
  const data = (await res.json()) as {
    ok: boolean
    results: SyncResultRow[]
  }
  for (const r of data.results || []) {
    if (r.ok) await removeOfflineOrder(r.client_id)
  }
  const conflicts = (data.results || []).filter((r) => !r.ok && r.status === 'conflict')
  const left = await listOfflineOrders()
  return {
    ok: data.ok,
    results: data.results || [],
    conflicts,
    pending_left: left.length,
  }
}

export function isOnline(): boolean {
  return typeof navigator !== 'undefined' ? navigator.onLine : true
}
