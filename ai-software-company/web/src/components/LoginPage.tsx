import { useState, type FormEvent } from 'react'
import { useAuth } from '../store/auth'

export function LoginPage() {
  const login = useAuth((s) => s.login)
  const [email, setEmail] = useState('cashier@example.com')
  const [password, setPassword] = useState('cashier123')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email.trim(), password)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Đăng nhập thất bại'
      const onPages = window.location.hostname.includes('github.io')
      setError(
        onPages
          ? `${msg}. Hãy mở POS tại http://127.0.0.1:8001 (chỉ cần email + mật khẩu).`
          : msg,
      )
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
          <h1 className="text-3xl font-bold text-white mt-2">Đăng nhập</h1>
          <p className="text-slate-400 mt-2 text-sm">Chỉ cần email và mật khẩu</p>
        </div>

        <label className="block text-slate-300 text-sm mb-1">Email / Tài khoản</label>
        <input
          className="w-full mb-4 rounded-xl bg-slate-950/60 border border-white/10 px-4 py-3 text-white outline-none focus:border-indigo-400"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="username"
          required
        />

        <label className="block text-slate-300 text-sm mb-1">Mật khẩu</label>
        <input
          type="password"
          className="w-full mb-6 rounded-xl bg-slate-950/60 border border-white/10 px-4 py-3 text-white outline-none focus:border-indigo-400"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />

        {error && (
          <div className="mb-4 rounded-xl bg-rose-500/15 border border-rose-400/30 text-rose-200 px-4 py-3 text-sm">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-xl bg-indigo-500 hover:bg-indigo-400 disabled:opacity-60 text-white font-semibold py-3.5 text-lg transition"
        >
          {loading ? 'Đang đăng nhập…' : 'Vào POS'}
        </button>

        <div className="mt-6 rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-xs text-slate-400 space-y-1">
          <p className="text-slate-300 font-medium">Tài khoản demo</p>
          <p>
            Thu ngân: <span className="text-indigo-200">cashier@example.com</span> /{' '}
            <span className="text-indigo-200">cashier123</span>
          </p>
          <p>
            Admin: <span className="text-indigo-200">admin@example.com</span> /{' '}
            <span className="text-indigo-200">admin123</span>
          </p>
        </div>
      </form>
    </div>
  )
}
