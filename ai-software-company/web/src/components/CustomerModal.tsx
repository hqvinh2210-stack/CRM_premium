import { useState } from 'react'
import { api, type Customer } from '../lib/api'
import { useAuth } from '../store/auth'

export function CustomerModal({
  open,
  onClose,
  onSelect,
}: {
  open: boolean
  onClose: () => void
  onSelect: (c: Customer) => void
}) {
  const { token, storeId } = useAuth()
  const [q, setQ] = useState('')
  const [name, setName] = useState('')
  const [results, setResults] = useState<Customer[]>([])
  const [error, setError] = useState('')

  if (!open) return null

  async function search() {
    if (!token || !storeId || !q.trim()) return
    setError('')
    try {
      setResults(await api.searchCustomers(token, storeId, q.trim()))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed')
    }
  }

  async function create() {
    if (!token || !storeId || !q.trim()) return
    setError('')
    try {
      const c = await api.createCustomer(token, storeId, q.trim(), name.trim() || q.trim())
      onSelect(c)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Create failed')
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="w-full max-w-lg rounded-2xl bg-slate-900 border border-white/10 p-5 shadow-2xl">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-white text-xl font-semibold">Khách hàng</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            Đóng
          </button>
        </div>

        <input
          placeholder="SĐT / tên"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void search()}
          className="w-full rounded-xl bg-slate-950 border border-white/10 px-3 py-3 text-white mb-2"
        />
        <input
          placeholder="Tên (khi tạo mới)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-xl bg-slate-950 border border-white/10 px-3 py-3 text-white mb-3"
        />

        <div className="flex gap-2 mb-4">
          <button
            onClick={() => void search()}
            className="flex-1 rounded-xl bg-indigo-500 text-white py-2.5 font-medium"
          >
            Tìm
          </button>
          <button
            onClick={() => void create()}
            className="flex-1 rounded-xl bg-emerald-600 text-white py-2.5 font-medium"
          >
            Tạo mới
          </button>
        </div>

        {error && <p className="text-rose-300 text-sm mb-2">{error}</p>}

        <div className="max-h-60 overflow-auto space-y-2">
          {results.map((c) => (
            <button
              key={c.id}
              onClick={() => {
                onSelect(c)
                onClose()
              }}
              className="w-full text-left rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 px-3 py-3"
            >
              <div className="text-white font-medium">{c.name || '—'}</div>
              <div className="text-slate-400 text-sm">{c.phone}</div>
            </button>
          ))}
          {!results.length && (
            <p className="text-slate-500 text-sm text-center py-4">Chưa có kết quả</p>
          )}
        </div>
      </div>
    </div>
  )
}
