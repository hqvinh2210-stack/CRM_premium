import { useCallback, useEffect, useState } from 'react'
import { api, money } from '../lib/api'
import { useAuth } from '../store/auth'

export function OpsPanel() {
  const { token, storeId, role } = useAuth()
  const [metrics, setMetrics] = useState<Awaited<ReturnType<typeof api.opsMetrics>> | null>(null)
  const [audit, setAudit] = useState<
    { action: string; detail?: string | null; created_at?: string | null; entity?: string | null }[]
  >([])
  const [staff, setStaff] = useState<
    { email: string; full_name?: string | null; role: string; is_active: boolean }[]
  >([])
  const [shiftNote, setShiftNote] = useState('')
  const [openingCash, setOpeningCash] = useState('0')
  const [closingCash, setClosingCash] = useState('0')
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  const isManager = role === 'admin' || role === 'manager'

  const refresh = useCallback(async () => {
    if (!token || !storeId) return
    setError('')
    try {
      const m = await api.opsMetrics(token, storeId)
      setMetrics(m)
      if (isManager) {
        const [a, s] = await Promise.all([
          api.opsAudit(token, storeId, 30),
          api.opsStaff(token, storeId),
        ])
        setAudit(a.items)
        setStaff(s.staff)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Load failed')
    }
  }, [token, storeId, isManager])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function openShift() {
    if (!token || !storeId) return
    try {
      await api.openShift(token, storeId, Number(openingCash) || 0, shiftNote || undefined)
      setMsg('Đã mở ca')
      setShiftNote('')
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Open shift failed')
    }
  }

  async function closeShift() {
    if (!token || !storeId || !metrics?.shift?.id) return
    try {
      const r = await api.closeShift(
        token,
        storeId,
        metrics.shift.id,
        Number(closingCash) || 0,
        shiftNote || undefined,
      )
      setMsg(`Đóng ca · variance ${r.variance ?? 0}`)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Close shift failed')
    }
  }

  async function downloadBackup() {
    if (!token || !storeId) return
    const res = await fetch(api.opsBackupUrl(), {
      headers: { Authorization: `Bearer ${token}`, 'X-Store-Id': storeId },
    })
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'crm_backup.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  async function downloadXlsx() {
    if (!token || !storeId) return
    const res = await fetch(api.exportXlsxUrl(7), {
      headers: { Authorization: `Bearer ${token}`, 'X-Store-Id': storeId },
    })
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'sales_7d.xls'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (!metrics && !error) {
    return <div className="p-6 text-slate-400">Đang tải ops…</div>
  }

  return (
    <div className="p-6 max-w-5xl space-y-6 overflow-auto h-full">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">Ops · Phase 5</h2>
          <p className="text-slate-400 text-sm">Metrics · Ca làm việc · Audit · Backup</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void refresh()}
            className="rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm"
          >
            Refresh
          </button>
          {role === 'admin' && (
            <button
              type="button"
              onClick={() => void downloadBackup()}
              className="rounded-lg bg-indigo-500/20 border border-indigo-400/30 text-indigo-100 px-3 py-2 text-sm"
            >
              Backup JSON
            </button>
          )}
          {isManager && (
            <button
              type="button"
              onClick={() => void downloadXlsx()}
              className="rounded-lg bg-emerald-500/20 border border-emerald-400/30 text-emerald-100 px-3 py-2 text-sm"
            >
              Excel 7 ngày
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-xl bg-rose-500/15 border border-rose-400/30 text-rose-200 px-4 py-3 text-sm">
          {error}
        </div>
      )}
      {msg && (
        <div className="rounded-xl bg-emerald-500/15 border border-emerald-400/30 text-emerald-100 px-4 py-3 text-sm">
          {msg}
        </div>
      )}

      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            ['Đơn hôm nay', String(metrics.orders_today)],
            ['Doanh thu', money(metrics.revenue_today)],
            ['Tiền mặt', money(metrics.cash_sales_today)],
            ['Tồn thấp', String(metrics.low_stock_skus)],
            ['KH total', String(metrics.customers_total)],
            ['Outbox', String(metrics.outbox.pending_or_failed)],
            ['DLQ', String(metrics.outbox.dead_letter)],
            ['Ca', metrics.shift ? 'OPEN' : '—'],
          ].map(([k, v]) => (
            <div key={k} className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-slate-400 text-xs uppercase tracking-wide">{k}</div>
              <div className="text-white text-xl font-bold mt-1">{v}</div>
            </div>
          ))}
        </div>
      )}

      <section className="rounded-2xl border border-white/10 bg-white/5 p-4 space-y-3">
        <h3 className="text-white font-semibold">Ca làm việc (shift)</h3>
        {metrics?.shift ? (
          <div className="text-sm text-slate-300 space-y-2">
            <p>
              Đang mở · opening {money(metrics.shift.opening_cash)} ·{' '}
              {metrics.shift.opened_at?.slice(0, 19)}
            </p>
            <div className="flex flex-wrap gap-2 items-center">
              <input
                className="rounded-lg bg-slate-950/60 border border-white/10 px-3 py-2 w-36"
                value={closingCash}
                onChange={(e) => setClosingCash(e.target.value)}
                placeholder="Tiền đếm cuối ca"
              />
              <input
                className="rounded-lg bg-slate-950/60 border border-white/10 px-3 py-2 flex-1 min-w-[140px]"
                value={shiftNote}
                onChange={(e) => setShiftNote(e.target.value)}
                placeholder="Ghi chú đóng ca"
              />
              <button
                type="button"
                onClick={() => void closeShift()}
                className="rounded-lg bg-amber-500/30 border border-amber-300/40 px-4 py-2 text-sm font-semibold"
              >
                Đóng ca
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2 items-center">
            <input
              className="rounded-lg bg-slate-950/60 border border-white/10 px-3 py-2 w-36"
              value={openingCash}
              onChange={(e) => setOpeningCash(e.target.value)}
              placeholder="Tiền đầu ca"
            />
            <input
              className="rounded-lg bg-slate-950/60 border border-white/10 px-3 py-2 flex-1 min-w-[140px]"
              value={shiftNote}
              onChange={(e) => setShiftNote(e.target.value)}
              placeholder="Ghi chú mở ca"
            />
            <button
              type="button"
              onClick={() => void openShift()}
              className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-semibold"
            >
              Mở ca
            </button>
          </div>
        )}
      </section>

      {isManager && staff.length > 0 && (
        <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <h3 className="text-white font-semibold mb-3">Nhân sự cửa hàng</h3>
          <ul className="space-y-2 text-sm">
            {staff.map((s) => (
              <li
                key={s.email}
                className="flex justify-between border-b border-white/5 pb-2 text-slate-300"
              >
                <span>
                  {s.full_name || s.email} · {s.email}
                </span>
                <span className="text-indigo-200">
                  {s.role}
                  {!s.is_active ? ' (off)' : ''}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {isManager && audit.length > 0 && (
        <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <h3 className="text-white font-semibold mb-3">Audit gần đây</h3>
          <ul className="space-y-2 text-xs max-h-64 overflow-auto">
            {audit.map((a, i) => (
              <li key={i} className="text-slate-400 border-b border-white/5 pb-1">
                <span className="text-indigo-200">{a.action}</span> · {a.entity} ·{' '}
                {a.created_at?.slice(0, 19)}
                {a.detail ? <div className="text-slate-500">{a.detail}</div> : null}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
