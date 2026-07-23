import { useCallback, useEffect, useState } from 'react'
import { api, money, type Product } from '../lib/api'
import { useAuth } from '../store/auth'

type LowItem = { product_id: string; sku: string; name: string; qty: number }

export function InventoryPanel() {
  const { token, storeId, stores, role } = useAuth()
  const [products, setProducts] = useState<Product[]>([])
  const [low, setLow] = useState<LowItem[]>([])
  const [threshold, setThreshold] = useState(10)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(false)

  // transfer form
  const [tProduct, setTProduct] = useState('')
  const [tToStore, setTToStore] = useState('')
  const [tQty, setTQty] = useState(1)

  // stocktake form
  const [sProduct, setSProduct] = useState('')
  const [sCounted, setSCounted] = useState(0)

  const canManage = role === 'manager' || role === 'admin'

  const reload = useCallback(async () => {
    if (!token || !storeId) return
    setLoading(true)
    setError('')
    try {
      const [plist, lowRes] = await Promise.all([
        api.products(token, storeId),
        api.lowStock(token, storeId, threshold),
      ])
      setProducts(plist)
      setLow(lowRes.items)
      if (!tProduct && plist[0]) setTProduct(plist[0].id)
      if (!sProduct && plist[0]) setSProduct(plist[0].id)
      const other = stores.find((s) => s.store_id !== storeId)
      if (!tToStore && other) setTToStore(other.store_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Load failed')
    } finally {
      setLoading(false)
    }
  }, [token, storeId, threshold, stores, tProduct, sProduct, tToStore])

  useEffect(() => {
    void reload()
  }, [reload])

  async function doTransfer() {
    if (!token || !storeId || !tProduct || !tToStore) return
    setError('')
    setMsg('')
    try {
      const r = await api.transferStock(token, storeId, {
        from_store_id: storeId,
        to_store_id: tToStore,
        product_id: tProduct,
        qty: tQty,
      })
      setMsg(`Transfer OK · ${r.qty} → store ${r.to_store_id.slice(0, 8)}`)
      await reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Transfer failed')
    }
  }

  async function doStocktake() {
    if (!token || !storeId || !sProduct) return
    setError('')
    setMsg('')
    try {
      const r = await api.stocktake(token, storeId, {
        product_id: sProduct,
        counted_qty: sCounted,
        apply_adjustment: true,
      })
      setMsg(`Stocktake OK · variance ${r.variance} (sys ${r.system_qty} → ${r.counted_qty})`)
      await reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Stocktake failed')
    }
  }

  return (
    <div className="h-full overflow-auto p-4 md:p-6 space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold text-white">Kho · Inventory</h1>
        <div className="flex items-center gap-2 ml-auto">
          <label className="text-xs text-slate-400">Low-stock ≤</label>
          <input
            type="number"
            min={0}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value) || 0)}
            className="w-20 rounded-lg bg-slate-900 border border-white/10 px-2 py-1.5 text-white text-sm"
          />
          <button
            onClick={() => void reload()}
            className="rounded-lg bg-indigo-500 px-3 py-1.5 text-sm font-medium"
          >
            Làm mới
          </button>
        </div>
      </div>

      {error && (
        <div className="text-rose-300 text-sm bg-rose-500/10 border border-rose-400/20 rounded-lg px-3 py-2">
          {error}
        </div>
      )}
      {msg && (
        <div className="text-emerald-200 text-sm bg-emerald-500/10 border border-emerald-400/20 rounded-lg px-3 py-2">
          {msg}
        </div>
      )}

      {/* Low stock */}
      <section className="rounded-2xl border border-amber-400/20 bg-amber-500/5 p-4">
        <h2 className="font-semibold text-amber-100 mb-3">
          Cảnh báo tồn thấp ({low.length})
        </h2>
        {!low.length && !loading && (
          <p className="text-sm text-slate-400">Không có SP dưới ngưỡng {threshold}</p>
        )}
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {low.map((i) => (
            <div
              key={i.product_id}
              className="rounded-xl border border-amber-400/20 bg-black/20 px-3 py-2 flex justify-between"
            >
              <div>
                <div className="text-white text-sm font-medium">{i.name}</div>
                <div className="text-xs text-slate-500">{i.sku}</div>
              </div>
              <div className="text-amber-200 font-bold text-lg">{i.qty}</div>
            </div>
          ))}
        </div>
      </section>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Transfer */}
        <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <h2 className="font-semibold text-white mb-3">Chuyển kho liên cửa hàng</h2>
          {!canManage && (
            <p className="text-xs text-slate-400 mb-2">Chỉ manager/admin được transfer</p>
          )}
          <div className="space-y-2">
            <select
              value={tProduct}
              onChange={(e) => setTProduct(e.target.value)}
              disabled={!canManage}
              className="w-full rounded-lg bg-slate-950 border border-white/10 px-3 py-2 text-white text-sm"
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · tồn {p.stock_qty ?? '—'}
                </option>
              ))}
            </select>
            <select
              value={tToStore}
              onChange={(e) => setTToStore(e.target.value)}
              disabled={!canManage}
              className="w-full rounded-lg bg-slate-950 border border-white/10 px-3 py-2 text-white text-sm"
            >
              {stores
                .filter((s) => s.store_id !== storeId)
                .map((s) => (
                  <option key={s.store_id} value={s.store_id}>
                    → {s.code} {s.name}
                  </option>
                ))}
            </select>
            {!stores.some((s) => s.store_id !== storeId) && (
              <p className="text-xs text-slate-500">
                Cần ≥2 cửa hàng trên tài khoản để transfer
              </p>
            )}
            <div className="flex gap-2">
              <input
                type="number"
                min={1}
                value={tQty}
                onChange={(e) => setTQty(Math.max(1, Number(e.target.value) || 1))}
                disabled={!canManage}
                className="w-24 rounded-lg bg-slate-950 border border-white/10 px-3 py-2 text-white text-sm"
              />
              <button
                onClick={() => void doTransfer()}
                disabled={!canManage || !tToStore}
                className="flex-1 rounded-lg bg-indigo-500 disabled:opacity-40 px-4 py-2 text-sm font-semibold"
              >
                Transfer
              </button>
            </div>
          </div>
        </section>

        {/* Stocktake */}
        <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <h2 className="font-semibold text-white mb-3">Kiểm kê (stocktake)</h2>
          <div className="space-y-2">
            <select
              value={sProduct}
              onChange={(e) => {
                setSProduct(e.target.value)
                const p = products.find((x) => x.id === e.target.value)
                setSCounted(Number(p?.stock_qty ?? 0))
              }}
              disabled={!canManage}
              className="w-full rounded-lg bg-slate-950 border border-white/10 px-3 py-2 text-white text-sm"
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · hệ thống {p.stock_qty ?? 0}
                </option>
              ))}
            </select>
            <div className="flex gap-2 items-center">
              <label className="text-xs text-slate-400 whitespace-nowrap">Đếm thực tế</label>
              <input
                type="number"
                min={0}
                value={sCounted}
                onChange={(e) => setSCounted(Math.max(0, Number(e.target.value) || 0))}
                disabled={!canManage}
                className="flex-1 rounded-lg bg-slate-950 border border-white/10 px-3 py-2 text-white text-sm"
              />
              <button
                onClick={() => void doStocktake()}
                disabled={!canManage}
                className="rounded-lg bg-emerald-600 disabled:opacity-40 px-4 py-2 text-sm font-semibold"
              >
                Áp dụng
              </button>
            </div>
          </div>
        </section>
      </div>

      {/* Stock table */}
      <section className="rounded-2xl border border-white/10 overflow-hidden">
        <div className="p-3 border-b border-white/10 text-sm text-slate-300 font-medium">
          Tồn kho cửa hàng hiện tại {loading ? '· loading…' : ''}
        </div>
        <table className="w-full text-sm">
          <thead className="bg-white/5 text-slate-400">
            <tr>
              <th className="text-left p-3">SKU</th>
              <th className="text-left p-3">Tên</th>
              <th className="text-right p-3">Giá</th>
              <th className="text-right p-3">Tồn</th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => {
              const qty = p.stock_qty ?? 0
              const warn = p.track_inventory !== false && qty <= threshold
              return (
                <tr key={p.id} className="border-t border-white/5">
                  <td className="p-3 text-slate-400 font-mono text-xs">{p.sku}</td>
                  <td className="p-3 text-white">{p.name}</td>
                  <td className="p-3 text-right text-slate-300">{money(p.price)}</td>
                  <td
                    className={`p-3 text-right font-bold ${
                      warn ? 'text-amber-300' : 'text-emerald-300'
                    }`}
                  >
                    {qty}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </section>
    </div>
  )
}
