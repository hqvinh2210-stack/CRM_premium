import { useState } from 'react'
import { api, money, type Customer, type Order } from '../lib/api'
import { enqueueOfflineOrder, isOnline } from '../lib/offline'
import { useAuth } from '../store/auth'
import { CustomerModal } from './CustomerModal'

export function CartPanel({
  order,
  setOrder,
  customer,
  setCustomer,
  discount,
  setDiscount,
  onPaid,
}: {
  order: Order | null
  setOrder: (o: Order | null) => void
  customer: Customer | null
  setCustomer: (c: Customer | null) => void
  discount: number
  setDiscount: (n: number) => void
  onPaid: (o: Order, receipt: string) => void
}) {
  const { token, storeId } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [showCust, setShowCust] = useState(false)
  const [promoCode, setPromoCode] = useState('')
  const [coach, setCoach] = useState('')
  const [points, setPoints] = useState<number | null>(null)

  const isLocal = !!order?.id?.startsWith('offline-')

  function localRecalc(lines: Order['lines'], pct: number): Order {
    const subtotal = lines.reduce((s, l) => s + Number(l.line_total), 0)
    const disc = (subtotal * pct) / 100
    return {
      ...(order as Order),
      lines,
      subtotal,
      discount: disc,
      total: Math.max(subtotal - disc, 0),
      discount_percent: pct,
    }
  }

  async function changeQty(lineId: string, qty: number) {
    if (!order) return
    setBusy(true)
    setError('')
    try {
      if (isLocal || !isOnline()) {
        let lines = order.lines.map((l) => ({ ...l }))
        const idx = lines.findIndex((l) => l.id === lineId)
        if (idx < 0) return
        if (qty < 1) lines = lines.filter((l) => l.id !== lineId)
        else {
          const unit = Number(lines[idx].unit_price)
          lines[idx] = { ...lines[idx], qty, line_total: unit * qty }
        }
        setOrder(localRecalc(lines, discount))
        return
      }
      if (!token || !storeId) return
      if (qty < 1) {
        setOrder(await api.deleteLine(token, storeId, order.id, lineId))
      } else {
        setOrder(await api.updateLine(token, storeId, order.id, lineId, qty))
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Update failed')
    } finally {
      setBusy(false)
    }
  }

  async function applyDiscount() {
    if (!order) return
    setBusy(true)
    try {
      if (isLocal || !isOnline()) {
        setOrder(localRecalc(order.lines, discount))
        return
      }
      if (!token || !storeId) return
      setOrder(
        await api.updateOrder(token, storeId, order.id, {
          discount_percent: discount,
          customer_id: customer?.id ?? null,
        }),
      )
      if (promoCode.trim() && !order.id.startsWith('offline-')) {
        await api.applyPromo(token, storeId, order.id, promoCode.trim())
        // reload order totals via pay path uses server; soft refresh by get not available — re-apply note
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Discount failed')
    } finally {
      setBusy(false)
    }
  }

  async function refreshCoach() {
    if (!token || !storeId || !order?.lines?.length || !isOnline()) return
    try {
      const rec = await api.recommend(
        token,
        storeId,
        order.lines.map((l) => l.product_id),
        customer?.id,
      )
      setCoach(rec.next_best_action || (rec.items[0] ? `Gợi ý: ${rec.items[0].name}` : ''))
    } catch {
      setCoach('')
    }
  }

  async function loadPoints(c: Customer) {
    if (!token || !storeId || !isOnline()) return
    try {
      const p = await api.loyaltyPoints(token, storeId, c.id)
      setPoints(p.balance)
    } catch {
      setPoints(null)
    }
  }

  async function attachCustomer(c: Customer) {
    setCustomer(c)
    void loadPoints(c)
    if (!order || isLocal || !isOnline()) return
    if (!token || !storeId) return
    try {
      setOrder(await api.updateOrder(token, storeId, order.id, { customer_id: c.id }))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Attach customer failed')
    }
  }

  async function pay() {
    if (!order?.lines?.length) return
    setBusy(true)
    setError('')
    try {
      if (!isOnline() || isLocal) {
        const clientId = crypto.randomUUID()
        const working = isLocal ? localRecalc(order.lines, discount) : order
        await enqueueOfflineOrder({
          client_id: clientId,
          customer_id: customer?.id ?? null,
          customer_phone: customer?.phone ?? null,
          discount_percent: discount,
          note: working.note,
          lines: working.lines.map((l) => ({
            product_id: l.product_id,
            qty: l.qty,
            unit_price: Number(l.unit_price),
            product_name: l.product_name,
          })),
          pay_method: 'cash',
          created_at: new Date().toISOString(),
        })
        const text = [
          '=== OFFLINE RECEIPT ===',
          `client: ${clientId.slice(0, 8)}`,
          ...working.lines.map((l) => `${l.product_name} x${l.qty}`),
          `TOTAL: ${working.total}`,
          'Sẽ sync khi online',
        ].join('\n')
        onPaid(working, text)
        setOrder(null)
        setCustomer(null)
        setDiscount(0)
        return
      }

      if (!token || !storeId) return
      if (discount !== Number(order.discount_percent || 0) || customer?.id) {
        await api.updateOrder(token, storeId, order.id, {
          discount_percent: discount,
          customer_id: customer?.id ?? null,
        })
      }
      if (promoCode.trim()) {
        await api.applyPromo(token, storeId, order.id, promoCode.trim())
      }
      void refreshCoach()
      const key = crypto.randomUUID()
      const paid = await api.pay(token, storeId, order.id, key, {
        promo_code: promoCode.trim() || undefined,
      })
      const receipt = await api.receipt(token, storeId, paid.id)
      onPaid(paid, receipt.text)
      setOrder(null)
      setCustomer(null)
      setDiscount(0)
    } catch (e) {
      if (order.lines?.length) {
        try {
          const clientId = crypto.randomUUID()
          await enqueueOfflineOrder({
            client_id: clientId,
            customer_id: customer?.id ?? null,
            customer_phone: customer?.phone ?? null,
            discount_percent: discount,
            lines: order.lines.map((l) => ({
              product_id: l.product_id,
              qty: l.qty,
              unit_price: Number(l.unit_price),
              product_name: l.product_name,
            })),
            pay_method: 'cash',
            created_at: new Date().toISOString(),
          })
          onPaid(order, `OFFLINE QUEUED\n${clientId}\n${e instanceof Error ? e.message : ''}`)
          setOrder(null)
          setCustomer(null)
          setDiscount(0)
          return
        } catch {
          /* fall through */
        }
      }
      setError(e instanceof Error ? e.message : 'Pay failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <aside className="h-full flex flex-col border-l border-white/10 bg-slate-950/60">
      <div className="p-4 border-b border-white/10">
        <h2 className="text-white text-xl font-bold">Giỏ hàng</h2>
        <button
          onClick={() => setShowCust(true)}
          className="mt-2 w-full text-left rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 hover:bg-white/10"
        >
          <div className="text-xs text-slate-400">Khách hàng</div>
          <div className="text-white font-medium">
            {customer ? `${customer.name || 'KH'} · ${customer.phone}` : 'Chọn / thêm khách'}
          </div>
        </button>
      </div>

      <div className="flex-1 overflow-auto p-3 space-y-2">
        {!order?.lines?.length && (
          <p className="text-slate-500 text-sm text-center py-10">Chạm sản phẩm để thêm</p>
        )}
        {order?.lines?.map((line) => (
          <div key={line.id} className="rounded-xl border border-white/10 bg-white/5 p-3">
            <div className="text-white font-medium">{line.product_name}</div>
            <div className="text-slate-400 text-xs mt-0.5">{money(line.unit_price)}</div>
            <div className="mt-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <button
                  className="h-9 w-9 rounded-lg bg-slate-800 text-white text-lg"
                  onClick={() => void changeQty(line.id, line.qty - 1)}
                >
                  −
                </button>
                <span className="text-white w-8 text-center font-semibold">{line.qty}</span>
                <button
                  className="h-9 w-9 rounded-lg bg-slate-800 text-white text-lg"
                  onClick={() => void changeQty(line.id, line.qty + 1)}
                >
                  +
                </button>
              </div>
              <span className="text-indigo-300 font-bold">{money(line.line_total)}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 border-t border-white/10 space-y-3">
        <div className="flex gap-2 items-center flex-wrap">
          <label className="text-slate-400 text-sm whitespace-nowrap">Giảm %</label>
          <input
            type="number"
            min={0}
            max={100}
            value={discount}
            onChange={(e) => setDiscount(Number(e.target.value))}
            className="w-16 rounded-lg bg-slate-900 border border-white/10 px-2 py-2 text-white"
          />
          <input
            placeholder="Mã KM"
            value={promoCode}
            onChange={(e) => setPromoCode(e.target.value)}
            className="w-24 rounded-lg bg-slate-900 border border-white/10 px-2 py-2 text-white text-sm"
          />
          <button
            onClick={() => void applyDiscount()}
            className="rounded-lg px-3 py-2 text-sm bg-white/5 border border-white/10 text-slate-200"
          >
            Áp dụng
          </button>
        </div>
        {points !== null && (
          <div className="text-xs text-amber-200">Điểm KH: {points}</div>
        )}
        {coach && (
          <div className="text-xs text-indigo-200 bg-indigo-500/10 border border-indigo-400/20 rounded-lg px-2 py-1.5">
            AI: {coach}
          </div>
        )}
        <button
          type="button"
          onClick={() => void refreshCoach()}
          className="text-xs text-slate-400 underline"
        >
          Gợi ý upsell
        </button>

        <div className="text-sm space-y-1">
          <div className="flex justify-between text-slate-400">
            <span>Tạm tính</span>
            <span>{money(order?.subtotal ?? 0)}</span>
          </div>
          <div className="flex justify-between text-slate-400">
            <span>Giảm</span>
            <span>-{money(order?.discount ?? 0)}</span>
          </div>
          <div className="flex justify-between text-white text-xl font-bold pt-1">
            <span>Tổng</span>
            <span className="text-indigo-300">{money(order?.total ?? 0)}</span>
          </div>
        </div>

        {error && (
          <div className="text-rose-300 text-sm bg-rose-500/10 border border-rose-400/20 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <button
          disabled={busy || !order?.lines?.length}
          onClick={() => void pay()}
          className="w-full rounded-2xl bg-emerald-500 hover:bg-emerald-400 text-white font-bold py-4 text-lg"
        >
          {busy ? 'Đang xử lý…' : isOnline() ? 'Thanh toán tiền mặt' : 'Lưu offline'}
        </button>
      </div>

      <CustomerModal
        open={showCust}
        onClose={() => setShowCust(false)}
        onSelect={(c) => void attachCustomer(c)}
      />
    </aside>
  )
}
