import { useEffect, useState } from 'react'
import { api, money, type Product } from '../lib/api'
import { useAuth } from '../store/auth'

export function ProductGrid({ onAdd }: { onAdd: (p: Product) => void }) {
  const { token, storeId } = useAuth()
  const [products, setProducts] = useState<Product[]>([])
  const [q, setQ] = useState('')
  const [barcode, setBarcode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function load(search?: string) {
    if (!token || !storeId) return
    setLoading(true)
    setError('')
    try {
      const list = await api.products(token, storeId, search)
      setProducts(list)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Load failed')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [token, storeId])

  async function onSearch() {
    await load(q.trim() || undefined)
  }

  async function onBarcodeEnter() {
    if (!token || !storeId || !barcode.trim()) return
    setError('')
    try {
      const p = await api.productByBarcode(token, storeId, barcode.trim())
      onAdd(p)
      setBarcode('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Barcode not found')
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="p-3 flex flex-wrap gap-2 border-b border-white/10">
        <input
          placeholder="Tìm tên / SKU…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void onSearch()}
          className="flex-1 min-w-[140px] rounded-xl bg-slate-950/70 border border-white/10 px-3 py-2.5 text-white"
        />
        <button
          onClick={() => void onSearch()}
          className="rounded-xl bg-slate-800 text-white px-4 py-2.5 border border-white/10"
        >
          Tìm
        </button>
        <input
          placeholder="Quét barcode + Enter"
          value={barcode}
          onChange={(e) => setBarcode(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void onBarcodeEnter()}
          className="flex-1 min-w-[160px] rounded-xl bg-indigo-950/40 border border-indigo-400/30 px-3 py-2.5 text-white"
        />
      </div>

      {error && (
        <div className="mx-3 mt-2 text-sm text-rose-300 bg-rose-500/10 border border-rose-400/20 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-auto p-3 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3 content-start">
        {loading && <div className="text-slate-400 col-span-full">Đang tải…</div>}
        {!loading &&
          products.map((p) => {
            const low = (p.stock_qty ?? 0) <= 10
            return (
              <button
                key={p.id}
                onClick={() => onAdd(p)}
                className="text-left rounded-2xl border border-white/10 bg-white/5 hover:bg-indigo-500/15 hover:border-indigo-400/40 p-4 transition active:scale-[0.98]"
              >
                <div className="text-white font-semibold text-base leading-snug min-h-[2.5rem]">
                  {p.name}
                </div>
                <div className="text-slate-400 text-xs mt-1">{p.sku}</div>
                <div className="mt-3 flex items-end justify-between gap-2">
                  <span className="text-indigo-300 font-bold text-lg">{money(p.price)}</span>
                  <span
                    className={`text-xs px-2 py-1 rounded-full ${
                      low
                        ? 'bg-amber-500/20 text-amber-200 border border-amber-400/30'
                        : 'bg-slate-800 text-slate-300'
                    }`}
                  >
                    Tồn {p.stock_qty ?? 0}
                  </span>
                </div>
              </button>
            )
          })}
      </div>
    </div>
  )
}
