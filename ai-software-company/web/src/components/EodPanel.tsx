import { useEffect, useState } from 'react'
import { api, money } from '../lib/api'
import { useAuth } from '../store/auth'

export function EodPanel() {
  const { token, storeId } = useAuth()
  const [data, setData] = useState<Awaited<ReturnType<typeof api.dailySales>> | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token || !storeId) return
    void api
      .dailySales(token, storeId)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed'))
  }, [token, storeId])

  if (error) return <div className="p-6 text-rose-300">{error}</div>
  if (!data) return <div className="p-6 text-slate-400">Đang tải báo cáo…</div>

  return (
    <div className="p-6 max-w-3xl">
      <h2 className="text-2xl font-bold text-white mb-1">Báo cáo cuối ngày</h2>
      <p className="text-slate-400 mb-6">{data.date}</p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        {[
          ['Đơn', String(data.order_count)],
          ['Gross', money(data.gross)],
          ['Giảm', money(data.discount)],
          ['Net', money(data.net)],
        ].map(([k, v]) => (
          <div key={k} className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="text-slate-400 text-xs uppercase tracking-wide">{k}</div>
            <div className="text-white text-xl font-bold mt-1">{v}</div>
          </div>
        ))}
      </div>

      <h3 className="text-white font-semibold mb-2">Theo phương thức</h3>
      <div className="rounded-xl border border-white/10 bg-white/5 p-4 mb-6 space-y-1">
        {Object.entries(data.by_payment_method || {}).map(([k, v]) => (
          <div key={k} className="flex justify-between text-slate-200">
            <span className="capitalize">{k}</span>
            <span>{money(v)}</span>
          </div>
        ))}
        {!Object.keys(data.by_payment_method || {}).length && (
          <p className="text-slate-500 text-sm">Chưa có thanh toán</p>
        )}
      </div>

      <h3 className="text-white font-semibold mb-2">Top sản phẩm</h3>
      <div className="rounded-xl border border-white/10 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-white/5 text-slate-400">
            <tr>
              <th className="text-left p-3">Tên</th>
              <th className="text-right p-3">SL</th>
              <th className="text-right p-3">DT</th>
            </tr>
          </thead>
          <tbody>
            {data.top_products.map((p) => (
              <tr key={p.name} className="border-t border-white/5 text-slate-200">
                <td className="p-3">{p.name}</td>
                <td className="p-3 text-right">{p.qty}</td>
                <td className="p-3 text-right">{money(p.revenue)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
