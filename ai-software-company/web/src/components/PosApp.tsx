import { useCallback, useState } from 'react'
import { api, type Customer, type Order, type OrderLine, type Product } from '../lib/api'
import { isOnline } from '../lib/offline'
import { useAuth } from '../store/auth'
import { CartPanel } from './CartPanel'
import { EodPanel } from './EodPanel'
import { ProductGrid } from './ProductGrid'
import { StoreBar } from './StoreBar'

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

function recalc(lines: OrderLine[], discountPercent: number): Pick<Order, 'subtotal' | 'discount' | 'total' | 'discount_percent'> {
  const subtotal = lines.reduce((s, l) => s + Number(l.line_total), 0)
  const discount = (subtotal * discountPercent) / 100
  return {
    subtotal,
    discount,
    total: Math.max(subtotal - discount, 0),
    discount_percent: discountPercent,
  }
}

export function PosApp() {
  const { token, storeId } = useAuth()
  const [view, setView] = useState<'pos' | 'eod'>('pos')
  const [order, setOrder] = useState<Order | null>(null)
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [receipt, setReceipt] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [discount, setDiscount] = useState(0)

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
              lines[idx] = {
                ...lines[idx],
                qty: q,
                line_total: unit * q,
              }
            } else {
              lines.push(localLine(p, 1))
            }
            const totals = recalc(lines, discount)
            return {
              id: prev?.id ?? `offline-${crypto.randomUUID()}`,
              status: 'draft',
              customer_id: customer?.id ?? null,
              note: prev?.note ?? null,
              lines,
              ...totals,
            }
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
    <div className="h-screen flex flex-col bg-slate-950 text-white">
      <StoreBar
        view={view}
        onEod={() => setView((v) => (v === 'eod' ? 'pos' : 'eod'))}
      />

      {error && (
        <div className="px-4 py-2 bg-rose-500/15 text-rose-200 text-sm border-b border-rose-400/20">
          {error}
        </div>
      )}

      {view === 'eod' ? (
        <div className="flex-1 overflow-auto">
          <EodPanel />
        </div>
      ) : (
        <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[1fr_380px]">
          <ProductGrid onAdd={(p) => void addProduct(p)} />
          <CartPanel
            order={order}
            setOrder={setOrder}
            customer={customer}
            setCustomer={setCustomer}
            discount={discount}
            setDiscount={setDiscount}
            onPaid={(_o, text) => setReceipt(text)}
          />
        </div>
      )}

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
