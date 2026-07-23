import { useEffect, useState } from 'react'
import { useI18n } from '../i18n'
import { listOfflineOrders, syncOfflineOrders } from '../lib/offline'
import { useAppNav, type AppModule } from '../store/app'
import { useAuth } from '../store/auth'

export function AppShell({ children }: { children: React.ReactNode }) {
  const { email, role, storeId, stores, selectStore, logout, token } = useAuth()
  const { module, setModule } = useAppNav()
  const { t, lang, setLang } = useI18n()
  const current = stores.find((s) => s.store_id === storeId)
  const [online, setOnline] = useState(navigator.onLine)
  const [pending, setPending] = useState(0)
  const [syncMsg, setSyncMsg] = useState('')

  const TABS: { id: AppModule; label: string }[] = [
    { id: 'pos', label: t('pos') },
    { id: 'crm', label: t('crm') },
    { id: 'inventory', label: t('inventory') },
    { id: 'eod', label: t('reports') },
  ]

  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    const tick = async () => {
      try {
        setPending((await listOfflineOrders()).length)
      } catch {
        setPending(0)
      }
    }
    void tick()
    const t = setInterval(() => void tick(), 5000)
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
        setSyncMsg(`Synced ${ok}`)
        setPending((await listOfflineOrders()).length)
        setTimeout(() => setSyncMsg(''), 3000)
      } catch (e) {
        setSyncMsg(e instanceof Error ? e.message : 'Sync error')
      }
    })()
  }, [online, token, storeId, pending])

  return (
    <div className="h-screen flex flex-col bg-slate-950 text-white">
      <header className="flex flex-wrap items-center gap-3 justify-between px-4 py-3 border-b border-white/10 bg-slate-950/90">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center text-indigo-200 font-bold text-xs">
            CRM
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
            {online ? t('online') : t('offline')}
            {pending > 0 ? ` · queue ${pending}` : ''}
          </span>
          {syncMsg && <span className="text-xs text-slate-400">{syncMsg}</span>}
        </div>

        <nav className="flex rounded-xl border border-white/10 bg-white/5 p-1 gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setModule(t.id)}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
                module === t.id
                  ? 'bg-indigo-500 text-white shadow'
                  : 'text-slate-300 hover:bg-white/10'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>

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
          <select
            className="rounded-lg bg-slate-900 border border-white/10 text-white px-2 py-2 text-xs"
            value={lang}
            onChange={(e) => setLang(e.target.value as 'vi' | 'en')}
            title={t('language')}
          >
            <option value="vi">VI</option>
            <option value="en">EN</option>
          </select>
          <button
            onClick={logout}
            className="rounded-lg px-3 py-2 text-sm bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10"
          >
            {t('logout')}
          </button>
        </div>
      </header>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  )
}
