import { useEffect, useState } from 'react'
import { listOfflineOrders, syncOfflineOrders } from '../lib/offline'
import { useAuth } from '../store/auth'

export function StoreBar({
  onEod,
  view,
}: {
  onEod: () => void
  view: 'pos' | 'eod'
}) {
  const { email, role, storeId, stores, selectStore, logout, token } = useAuth()
  const current = stores.find((s) => s.store_id === storeId)
  const [online, setOnline] = useState(navigator.onLine)
  const [pending, setPending] = useState(0)
  const [syncMsg, setSyncMsg] = useState('')

  async function refreshPending() {
    try {
      setPending((await listOfflineOrders()).length)
    } catch {
      setPending(0)
    }
  }

  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    void refreshPending()
    const t = setInterval(() => void refreshPending(), 5000)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
      clearInterval(t)
    }
  }, [])

  useEffect(() => {
    if (!online || !token || !storeId || pending === 0) return
    void (async () => {
      try {
        const r = await syncOfflineOrders(token, storeId)
        const ok = r.results.filter((x) => x.ok).length
        const fail = r.results.filter((x) => !x.ok).length
        setSyncMsg(`Synced ${ok}${fail ? `, fail ${fail}` : ''}`)
        await refreshPending()
        setTimeout(() => setSyncMsg(''), 4000)
      } catch (e) {
        setSyncMsg(e instanceof Error ? e.message : 'Sync error')
      }
    })()
  }, [online, token, storeId, pending])

  return (
    <header className="flex flex-wrap items-center gap-3 justify-between px-4 py-3 border-b border-white/10 bg-slate-950/80">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center text-indigo-200 font-bold">
          POS
        </div>
        <div>
          <div className="text-white font-semibold leading-tight">
            {current?.name ?? 'Cửa hàng'}
          </div>
          <div className="text-slate-400 text-xs">
            {email} · {role}
          </div>
        </div>
        <span
          className={`text-xs px-2 py-1 rounded-full border ${
            online
              ? 'bg-emerald-500/15 text-emerald-200 border-emerald-400/30'
              : 'bg-amber-500/15 text-amber-200 border-amber-400/30'
          }`}
        >
          {online ? 'Online' : 'Offline'}
          {pending > 0 ? ` · queue ${pending}` : ''}
        </span>
        {syncMsg && <span className="text-xs text-slate-400">{syncMsg}</span>}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select
          className="rounded-lg bg-slate-900 border border-white/10 text-white px-3 py-2 text-sm"
          value={storeId ?? ''}
          onChange={(e) => selectStore(e.target.value)}
        >
          {stores.map((s) => (
            <option key={s.store_id} value={s.store_id}>
              {s.code} — {s.name}
            </option>
          ))}
        </select>

        <button
          onClick={onEod}
          className={`rounded-lg px-3 py-2 text-sm font-medium border ${
            view === 'eod'
              ? 'bg-emerald-500/20 border-emerald-400/40 text-emerald-200'
              : 'bg-white/5 border-white/10 text-slate-200 hover:bg-white/10'
          }`}
        >
          Cuối ngày
        </button>
        <button
          onClick={logout}
          className="rounded-lg px-3 py-2 text-sm bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10"
        >
          Thoát
        </button>
      </div>
    </header>
  )
}
