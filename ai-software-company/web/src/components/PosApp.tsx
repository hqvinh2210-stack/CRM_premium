import { useCallback, useEffect, useState } from 'react'
import { api, type Customer, type Order, type OrderLine, type Product } from '../lib/api'
import {
  isOnline,
  listOfflineOrders,
  syncOfflineOrders,
  type SyncResultRow,
} from '../lib/offline'
import { useAppNav } from '../store/app'
import { useAuth } from '../store/auth'
import { CartPanel } from './CartPanel'
import { ProductGrid } from './ProductGrid'

function localLine(p: Product, qty = 1): OrderLine {
  const price = Number(p.price)
  return {
    id: `local-${p.id}`,
    product_id: p.id,
    product_name: p.name,
    qty,
    unit_price: price,
    line_discount: 0,
    line_total: price * qty,
  }
}

function recalc(
  lines: OrderLine[],
  discountPercent: number,
  base?: Partial<Order>,
): Order {
  const subtotal = lines.reduce((s, l) => s + Number(l.line_total), 0)
  const discount = (subtotal * discountPercent) / 100
  return {
    id: base?.id ?? `offline-${crypto.randomUUID()}`,
    status: 'draft',
    customer_id: base?.customer_id ?? null,
    note: base?.note ?? null,
    lines,
    subtotal,
    discount,
    total: Math.max(subtotal - discount, 0),
    discount_percent: discountPercent,
  }
}

export function PosApp() {
  const { token, storeId } = useAuth()
  const { posCustomer, clearPosCustomer, openCrmProfile, setModule } = useAppNav()
  const [order, setOrder] = useState<Order | null>(null)
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [receipt, setReceipt] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [discount, setDiscount] = useState(0)
  const [offlineCount, setOfflineCount] = useState(0)
  const [conflicts, setConflicts] = useState<SyncResultRow[]>([])
  const [syncMsg, setSyncMsg] = useState('')

  // CRM → POS: preselect customer
  useEffect(() => {
    if (posCustomer) {
      setCustomer(posCustomer)
    }
  }, [posCustomer])

  const refreshOffline = useCallback(async () => {
    try {
      const rows = await listOfflineOrders()
      setOfflineCount(rows.length)
    } catch {
      setOfflineCount(0)
    }
  }, [])

  useEffect(() => {
    void refreshOffline()
    const onOnline = () => void refreshOffline()
    window.addEventListener('online', onOnline)
    return () => window.removeEventListener('online', onOnline)
  }, [refreshOffline])

  async function handleSyncOffline() {
    if (!token || !storeId) return
    setSyncMsg('Đang sync offline…')
    setConflicts([])
    try {
      const r = await syncOfflineOrders(token, storeId)
      setConflicts(r.conflicts)
      setOfflineCount(r.pending_left)
      if (r.conflicts.length) {
        setSyncMsg(
          `Sync xong: ${r.results.filter((x) => x.ok).length} OK, ${r.conflicts.length} conflict (server price / stock) — cần xử lý tay.`,
        )
      } else {
        setSyncMsg(r.ok ? 'Sync offline thành công.' : 'Sync một phần thất bại.')
      }
    } catch (e) {
      setSyncMsg(e instanceof Error ? e.message : 'Sync failed')
    }
  }

  const addProduct = useCallback(
    async (p: Product) => {
      if (!token || !storeId) return
      setError('')
      try {
        if (!isOnline()) {
          setOrder((prev) => {
            const lines = [...(prev?.lines ?? [])]
            const idx = lines.findIndex((l) => l.product_id === p.id)
            if (idx >= 0) {
              const q = lines[idx].qty + 1
              const unit = Number(lines[idx].unit_price)
              lines[idx] = { ...lines[idx], qty: q, line_total: unit * q }
            } else {
              lines.push(localLine(p, 1))
            }
            return recalc(lines, discount, {
              id: prev?.id,
              customer_id: customer?.id ?? prev?.customer_id,
            })
          })
          return
        }

        let o = order
        if (!o || o.id.startsWith('offline-')) {
          o = await api.createOrder(token, storeId, customer?.id)
          setOrder(o)
        }
        const next = await api.addLine(token, storeId, o.id, p.id, 1)
        setOrder(next)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Không thêm được SP')
      }
    },
    [token, storeId, order, customer, discount],
  )

  return (
    <div className="h-full flex flex-col min-h-0">
      {(offlineCount > 0 || conflicts.length > 0 || syncMsg) && (
        <div className="px-4 py-2 border-b border-amber-400/30 bg-amber-500/10 text-sm space-y-1">
          <div className="flex flex-wrap items-center gap-2 text-amber-100">
            <span>
              Offline queue: <strong>{offlineCount}</strong>
              {!isOnline() ? ' · đang offline' : ''}
            </span>
            {isOnline() && offlineCount > 0 && (
              <button
                type="button"
                onClick={() => void handleSyncOffline()}
                className="rounded-lg bg-amber-500/30 border border-amber-300/40 px-2 py-1 text-xs"
              >
                Sync ngay
              </button>
            )}
            {syncMsg && <span className="text-amber-50/90 text-xs">{syncMsg}</span>}
          </div>
          {conflicts.length > 0 && (
            <ul className="text-xs text-rose-200 list-disc pl-4">
              {conflicts.map((c) => (
                <li key={c.client_id}>
                  {c.client_id.slice(0, 8)}… · {c.error || c.status} · resolution=
                  {c.resolution || 'manual_resolve'}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {customer && (
        <div className="px-4 py-2 border-b border-emerald-400/20 bg-emerald-500/10 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-emerald-200">
            Đang bán cho: <strong>{customer.name || 'KH'}</strong> · {customer.phone}
          </span>
          <button
            className="text-indigo-300 underline text-xs"
            onClick={() => openCrmProfile(customer.id)}
          >
            Mở CRM
          </button>
          <button
            className="text-slate-400 underline text-xs ml-auto"
            onClick={() => {
              setCustomer(null)
              clearPosCustomer()
            }}
          >
            Bỏ chọn KH
          </button>
          <button
            className="text-slate-400 underline text-xs"
            onClick={() => setModule('crm')}
          >
            ← CRM
          </button>
        </div>
      )}

      {error && (
        <div className="px-4 py-2 bg-rose-500/15 text-rose-200 text-sm border-b border-rose-400/20">
          {error}
        </div>
      )}

      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[1fr_380px]">
        <ProductGrid onAdd={(p) => void addProduct(p)} />
        <CartPanel
          order={order}
          setOrder={setOrder}
          customer={customer}
          setCustomer={(c) => {
            setCustomer(c)
            if (!c) clearPosCustomer()
          }}
          discount={discount}
          setDiscount={setDiscount}
          onPaid={(_o, text) => setReceipt(text)}
        />
      </div>

      {receipt && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-white/10 p-5">
            <h3 className="text-white font-bold text-lg mb-3">Hóa đơn</h3>
            <pre className="text-slate-200 text-xs whitespace-pre-wrap bg-black/40 rounded-xl p-4 max-h-[60vh] overflow-auto font-mono">
              {receipt}
            </pre>
            <button
              className="mt-4 w-full rounded-xl bg-indigo-500 py-3 font-semibold"
              onClick={() => setReceipt(null)}
            >
              Đóng · Đơn mới
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
