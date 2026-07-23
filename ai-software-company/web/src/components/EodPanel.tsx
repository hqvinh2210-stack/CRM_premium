import { useEffect, useState } from 'react'
import { api, money } from '../lib/api'
import { useAuth } from '../store/auth'

export function EodPanel() {
  const { token, storeId } = useAuth()
  const [data, setData] = useState<Awaited<ReturnType<typeof api.dailySales>> | null>(null)
  const [analytics, setAnalytics] = useState<Awaited<ReturnType<typeof api.analytics>> | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token || !storeId) return
    void Promise.all([api.dailySales(token, storeId), api.analytics(token, storeId, 7)])
      .then(([d, a]) => {
        setData(d)
        setAnalytics(a)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed'))
  }, [token, storeId])

  if (error) return <div className="p-6 text-rose-300">{error}</div>
  if (!data) return <div className="p-6 text-slate-400">Đang tải báo cáo…</div>

  const maxDayRev = Math.max(
    ...(analytics?.by_day.map((d) => Number(d.revenue) || 0) ?? [0]),
    1,
  )

  return (
    <div className="p-6 max-w-4xl space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white mb-1">Báo cáo cuối ngày</h2>
          <p className="text-slate-400">{data.date}</p>
        </div>
        <div className="flex gap-2">
          <a
            href={api.exportCsvUrl(7)}
            className="rounded-lg bg-indigo-500/20 border border-indigo-400/30 text-indigo-100 px-3 py-2 text-sm font-medium"
            onClick={async (e) => {
              e.preventDefault()
              if (!token || !storeId) return
              const res = await fetch(api.exportCsvUrl(7), {
                headers: { Authorization: `Bearer ${token}`, 'X-Store-Id': storeId },
              })
              const blob = await res.blob()
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = 'sales_7d.csv'
              a.click()
              URL.revokeObjectURL(url)
            }}
          >
            Xuất CSV
          </a>
          <a
            href="/api/v1/reports/export.txt"
            className="rounded-lg bg-white/5 border border-white/10 text-slate-200 px-3 py-2 text-sm"
            onClick={async (e) => {
              e.preventDefault()
              if (!token || !storeId) return
              const res = await fetch('/api/v1/reports/export.txt', {
                headers: { Authorization: `Bearer ${token}`, 'X-Store-Id': storeId },
              })
              const text = await res.text()
              const blob = new Blob([text], { type: 'text/plain' })
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = 'eod.txt'
              a.click()
              URL.revokeObjectURL(url)
            }}
          >
            Xuất TXT
          </a>
          <button
            type="button"
            className="rounded-lg bg-emerald-500/20 border border-emerald-400/30 text-emerald-100 px-3 py-2 text-sm font-medium"
            onClick={async () => {
              if (!token || !storeId) return
              const res = await fetch(api.exportPdfUrl(), {
                headers: { Authorization: `Bearer ${token}`, 'X-Store-Id': storeId },
              })
              const blob = await res.blob()
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = 'eod.pdf'
              a.click()
              URL.revokeObjectURL(url)
            }}
          >
            Xuất PDF
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
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

      {analytics && (
        <section>
          <h3 className="text-white font-semibold mb-3">Analytics 7 ngày</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            {[
              ['Doanh thu', money(analytics.totals.revenue)],
              ['Đơn', String(analytics.totals.order_count)],
              ['AOV', money(analytics.totals.avg_order_value)],
              ['CLV proxy', money(analytics.totals.clv_proxy_avg)],
            ].map(([k, v]) => (
              <div key={k} className="rounded-xl border border-indigo-400/20 bg-indigo-500/10 p-3">
                <div className="text-indigo-200/70 text-xs">{k}</div>
                <div className="text-white font-bold mt-0.5">{v}</div>
              </div>
            ))}
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-end gap-1 h-28">
              {analytics.by_day.map((d) => {
                const rev = Number(d.revenue) || 0
                const h = Math.max(4, Math.round((rev / maxDayRev) * 100))
                return (
                  <div key={d.date} className="flex-1 flex flex-col items-center gap-1 h-full justify-end">
                    <div
                      className="w-full rounded-t bg-indigo-500/70 min-h-[4px]"
                      style={{ height: `${h}%` }}
                      title={`${d.date}: ${money(d.revenue)}`}
                    />
                    <span className="text-[9px] text-slate-500">
                      {d.date.slice(5)}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        </section>
      )}

      <section>
        <h3 className="text-white font-semibold mb-2">Theo phương thức</h3>
        <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-1">
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
      </section>

      <section>
        <h3 className="text-white font-semibold mb-2">Top sản phẩm (hôm nay)</h3>
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
      </section>
    </div>
  )
}
