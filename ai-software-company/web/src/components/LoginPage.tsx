import { useState, type FormEvent } from 'react'
import { getApiBase, setApiBase } from '../lib/api'
import { useAuth } from '../store/auth'

export function LoginPage() {
  const login = useAuth((s) => s.login)
  const [email, setEmail] = useState('cashier@example.com')
  const [password, setPassword] = useState('cashier123')
  const [apiBase, setApiBaseInput] = useState(() => getApiBase() || 'http://127.0.0.1:8001')
  const [showApi, setShowApi] = useState(() => !getApiBase() && import.meta.env.PROD)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      // Persist API origin before login (needed on GitHub Pages)
      setApiBase(apiBase)
      await login(email, password)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Login failed'
      setError(
        msg +
          (import.meta.env.PROD
            ? ' — kiểm tra API URL bên dưới (backend public + CORS).'
            : ''),
      )
      setShowApi(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl p-8 shadow-2xl"
      >
        <div className="mb-8">
          <p className="text-indigo-300 text-sm font-semibold tracking-widest uppercase">
            CRM Premium POS
          </p>
          <h1 className="text-3xl font-bold text-white mt-2">Đăng nhập quầy</h1>
          <p className="text-slate-400 mt-2 text-sm">Multi-store · SoftPOS · GitHub Pages ready</p>
        </div>

        <label className="block text-slate-300 text-sm mb-1">Email</label>
        <input
          className="w-full mb-4 rounded-xl bg-slate-950/60 border border-white/10 px-4 py-3 text-white outline-none focus:border-indigo-400"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="username"
        />

        <label className="block text-slate-300 text-sm mb-1">Mật khẩu</label>
        <input
          type="password"
          className="w-full mb-4 rounded-xl bg-slate-950/60 border border-white/10 px-4 py-3 text-white outline-none focus:border-indigo-400"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />

        <button
          type="button"
          className="text-xs text-indigo-300 underline mb-2"
          onClick={() => setShowApi((v) => !v)}
        >
          {showApi ? 'Ẩn' : 'Hiện'} API server (GH Pages)
        </button>
        {showApi && (
          <div className="mb-4">
            <label className="block text-slate-300 text-sm mb-1">API base URL</label>
            <input
              className="w-full rounded-xl bg-slate-950/60 border border-white/10 px-4 py-3 text-white outline-none focus:border-indigo-400 text-sm"
              value={apiBase}
              onChange={(e) => setApiBaseInput(e.target.value)}
              placeholder="http://127.0.0.1:8001 hoặc https://api.example.com"
            />
            <p className="text-slate-500 text-[11px] mt-1">
              Backend Docker local: http://127.0.0.1:8001 · Cần CORS_ORIGINS cho domain Pages.
            </p>
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-xl bg-rose-500/15 border border-rose-400/30 text-rose-200 px-4 py-3 text-sm">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-xl bg-indigo-500 hover:bg-indigo-400 text-white font-semibold py-3.5 text-lg transition"
        >
          {loading ? 'Đang đăng nhập…' : 'Vào POS'}
        </button>

        <p className="text-slate-500 text-xs mt-6 text-center">
          Demo: cashier@example.com / cashier123
        </p>
      </form>
    </div>
  )
}
