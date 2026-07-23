import { useCallback, useEffect, useState } from 'react'
import { api, money, type Customer, type CustomerProfile } from '../../lib/api'
import { useAppNav } from '../../store/app'
import { useAuth } from '../../store/auth'

export function CrmApp() {
  const { token, storeId } = useAuth()
  const { crmCustomerId, openCrmProfile, clearCrmProfile, sellToCustomer } = useAppNav()
  const [q, setQ] = useState('')
  const [list, setList] = useState<Customer[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [profile, setProfile] = useState<CustomerProfile | null>(null)
  const [tab, setTab] = useState<'directory' | 'rfm'>('directory')
  const [rfm, setRfm] = useState<
    { customer_id: string; name: string; phone: string; segment: string; frequency: number; monetary: string; recency_days: number }[]
  >([])
  const [newPhone, setNewPhone] = useState('')
  const [newName, setNewName] = useState('')
  const [notes, setNotes] = useState('')
  const [timeline, setTimeline] = useState<
    { at: string | null; kind: string; title: string; ref_id: string }[]
  >([])
  const [profileTab, setProfileTab] = useState<'orders' | 'timeline' | 'tasks'>('orders')
  const [tasks, setTasks] = useState<{ id: string; title: string; status: string; notes?: string | null }[]>(
    [],
  )
  const [newTask, setNewTask] = useState('')

  const loadList = useCallback(async () => {
    if (!token || !storeId) return
    setLoading(true)
    setError('')
    try {
      setList(await api.listCustomers(token, storeId, q || undefined))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Load failed')
    } finally {
      setLoading(false)
    }
  }, [token, storeId, q])

  const loadProfile = useCallback(
    async (id: string) => {
      if (!token || !storeId) return
      setError('')
      try {
        const [p, tl, tk] = await Promise.all([
          api.customerProfile(token, storeId, id),
          api.customerTimeline(token, storeId, id),
          api.listTasks(token, storeId, id, 'open'),
        ])
        setProfile(p)
        setNotes(p.customer.notes || '')
        setTimeline(tl.events)
        setTasks(tk.tasks)
        setProfileTab('orders')
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Profile failed')
      }
    },
    [token, storeId],
  )

  async function addTask() {
    if (!token || !storeId || !profile || !newTask.trim()) return
    try {
      await api.createTask(token, storeId, {
        customer_id: profile.customer.id,
        title: newTask.trim(),
      })
      setNewTask('')
      const tk = await api.listTasks(token, storeId, profile.customer.id, 'open')
      setTasks(tk.tasks)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Task failed')
    }
  }

  async function completeTask(id: string) {
    if (!token || !storeId || !profile) return
    try {
      await api.updateTask(token, storeId, id, { status: 'done' })
      const tk = await api.listTasks(token, storeId, profile.customer.id, 'open')
      setTasks(tk.tasks)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Update failed')
    }
  }

  useEffect(() => {
    if (tab === 'directory' && !crmCustomerId) void loadList()
  }, [tab, crmCustomerId, loadList])

  useEffect(() => {
    if (crmCustomerId) void loadProfile(crmCustomerId)
    else setProfile(null)
  }, [crmCustomerId, loadProfile])

  async function loadRfm() {
    if (!token || !storeId) return
    setLoading(true)
    try {
      const r = await api.rfm(token, storeId)
      setRfm(r.segments)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'RFM failed')
    } finally {
      setLoading(false)
    }
  }

  async function createCustomer() {
    if (!token || !storeId || !newPhone.trim()) return
    try {
      const c = await api.createCustomer(token, storeId, newPhone.trim(), newName.trim() || newPhone.trim())
      setNewPhone('')
      setNewName('')
      await loadList()
      openCrmProfile(c.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Create failed')
    }
  }

  async function saveNotes() {
    if (!token || !storeId || !profile) return
    try {
      await api.updateCustomer(token, storeId, profile.customer.id, { notes })
      await loadProfile(profile.customer.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    }
  }

  // Profile view
  if (crmCustomerId && profile) {
    const c = profile.customer
    const s = profile.stats
    return (
      <div className="h-full overflow-auto p-4 md:p-6">
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <button
            onClick={() => clearCrmProfile()}
            className="rounded-lg px-3 py-2 text-sm border border-white/10 bg-white/5 hover:bg-white/10"
          >
            ← Danh sách
          </button>
          <h1 className="text-2xl font-bold text-white">{c.name || 'Khách hàng'}</h1>
          <span className="text-xs px-2 py-1 rounded-full bg-indigo-500/20 text-indigo-200 border border-indigo-400/30">
            {s.segment}
          </span>
          <button
            onClick={() =>
              sellToCustomer({
                id: c.id,
                phone: c.phone,
                name: c.name,
                email: c.email,
              })
            }
            className="ml-auto rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white font-semibold px-4 py-2.5"
          >
            Bán hàng cho KH này → POS
          </button>
        </div>

        {error && (
          <div className="mb-4 text-rose-300 text-sm bg-rose-500/10 border border-rose-400/20 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <div className="grid md:grid-cols-4 gap-3 mb-6">
          {[
            ['SĐT', c.phone],
            ['Điểm', String(profile.points.balance)],
            ['Số đơn', String(s.order_count)],
            ['Tổng chi', money(s.total_spend)],
          ].map(([k, v]) => (
            <div key={k} className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-slate-400 text-xs uppercase">{k}</div>
              <div className="text-white text-lg font-bold mt-1">{v}</div>
            </div>
          ))}
        </div>

        <div className="grid lg:grid-cols-2 gap-4">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <h2 className="font-semibold text-white mb-2">Ghi chú CRM</h2>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
              className="w-full rounded-xl bg-slate-950 border border-white/10 p-3 text-white text-sm"
              placeholder="Ghi chú follow-up..."
            />
            <button
              onClick={() => void saveNotes()}
              className="mt-2 rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium"
            >
              Lưu ghi chú
            </button>
            <div className="mt-4 text-xs text-slate-400 space-y-1">
              <div>Email: {c.email || '—'}</div>
              <div>Mua gần nhất: {s.last_purchase ? new Date(s.last_purchase).toLocaleString('vi-VN') : '—'}</div>
              <div>Recency: {s.recency_days ?? '—'} ngày</div>
              <div>Lifetime earned: {profile.points.lifetime_earned}</div>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center gap-2 mb-3">
              <button
                onClick={() => setProfileTab('orders')}
                className={`text-sm px-2 py-1 rounded-md ${
                  profileTab === 'orders' ? 'bg-indigo-500 text-white' : 'text-slate-400'
                }`}
              >
                Lịch sử mua
              </button>
              <button
                onClick={() => setProfileTab('timeline')}
                className={`text-sm px-2 py-1 rounded-md ${
                  profileTab === 'timeline' ? 'bg-indigo-500 text-white' : 'text-slate-400'
                }`}
              >
                Timeline
              </button>
              <button
                onClick={() => setProfileTab('tasks')}
                className={`text-sm px-2 py-1 rounded-md ${
                  profileTab === 'tasks' ? 'bg-indigo-500 text-white' : 'text-slate-400'
                }`}
              >
                Follow-up
              </button>
            </div>
            <div className="space-y-2 max-h-[50vh] overflow-auto">
              {profileTab === 'orders' && (
                <>
                  {!profile.orders.length && (
                    <p className="text-slate-500 text-sm">Chưa có đơn paid tại cửa hàng này</p>
                  )}
                  {profile.orders.map((o) => (
                    <div key={o.id} className="rounded-xl border border-white/10 bg-black/20 p-3">
                      <div className="flex justify-between text-sm">
                        <span className="text-slate-300">
                          {o.paid_at ? new Date(o.paid_at).toLocaleString('vi-VN') : o.id.slice(0, 8)}
                        </span>
                        <span className="text-indigo-300 font-bold">{money(o.total)}</span>
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        {o.lines.map((l) => `${l.product_name}×${l.qty}`).join(', ')}
                      </div>
                      {o.status === 'paid' && (
                        <div className="flex gap-2 mt-2">
                          <button
                            className="text-[11px] text-emerald-300 hover:underline"
                            onClick={() =>
                              void api
                                .issueEinvoice(token!, storeId!, o.id)
                                .then((r) => setError(`E-invoice: ${r.invoice_no}`))
                                .catch((e) =>
                                  setError(e instanceof Error ? e.message : 'Invoice fail'),
                                )
                            }
                          >
                            E-invoice
                          </button>
                          <button
                            className="text-[11px] text-sky-300 hover:underline"
                            onClick={() =>
                              void api
                                .notifyOrder(token!, storeId!, o.id, c.phone)
                                .then((r) => setError(`Notify ${r.channel}: ${r.status}`))
                                .catch((e) =>
                                  setError(e instanceof Error ? e.message : 'Notify fail'),
                                )
                            }
                          >
                            SMS/Zalo
                          </button>
                          <button
                            className="text-[11px] text-rose-300 hover:underline"
                            onClick={() =>
                              void api
                                .refund(token!, storeId!, o.id, 'CRM refund')
                                .then(() => loadProfile(c.id))
                                .catch((e) =>
                                  setError(e instanceof Error ? e.message : 'Refund fail'),
                                )
                            }
                          >
                            Refund
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </>
              )}
              {profileTab === 'timeline' && (
                <>
                  {!timeline.length && (
                    <p className="text-slate-500 text-sm">Chưa có sự kiện timeline</p>
                  )}
                  {timeline.map((e) => (
                    <div
                      key={`${e.kind}-${e.ref_id}`}
                      className="rounded-xl border border-white/10 bg-black/20 p-3"
                    >
                      <div className="flex justify-between text-xs text-slate-500 mb-1">
                        <span className="font-mono text-indigo-300/80">{e.kind}</span>
                        <span>
                          {e.at ? new Date(e.at).toLocaleString('vi-VN') : '—'}
                        </span>
                      </div>
                      <div className="text-sm text-white">{e.title}</div>
                    </div>
                  ))}
                </>
              )}
              {profileTab === 'tasks' && (
                <>
                  <div className="flex gap-2 mb-2">
                    <input
                      value={newTask}
                      onChange={(e) => setNewTask(e.target.value)}
                      placeholder="Follow-up task..."
                      className="flex-1 rounded-lg bg-slate-950 border border-white/10 px-3 py-2 text-sm text-white"
                    />
                    <button
                      onClick={() => void addTask()}
                      className="rounded-lg bg-indigo-500 px-3 py-2 text-sm font-medium"
                    >
                      Thêm
                    </button>
                  </div>
                  {!tasks.length && (
                    <p className="text-slate-500 text-sm">Chưa có task mở</p>
                  )}
                  {tasks.map((tk) => (
                    <div
                      key={tk.id}
                      className="rounded-xl border border-white/10 bg-black/20 p-3 flex justify-between gap-2"
                    >
                      <div className="text-sm text-white">{tk.title}</div>
                      <button
                        onClick={() => void completeTask(tk.id)}
                        className="text-xs text-emerald-300 hover:underline whitespace-nowrap"
                      >
                        Done
                      </button>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Directory / RFM
  return (
    <div className="h-full overflow-auto p-4 md:p-6">
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold text-white">CRM · Khách hàng</h1>
        <div className="flex rounded-lg border border-white/10 p-0.5 bg-white/5">
          <button
            onClick={() => {
              setTab('directory')
              clearCrmProfile()
            }}
            className={`px-3 py-1.5 rounded-md text-sm ${tab === 'directory' ? 'bg-indigo-500' : 'text-slate-300'}`}
          >
            Danh bạ
          </button>
          <button
            onClick={() => {
              setTab('rfm')
              clearCrmProfile()
              void loadRfm()
            }}
            className={`px-3 py-1.5 rounded-md text-sm ${tab === 'rfm' ? 'bg-indigo-500' : 'text-slate-300'}`}
          >
            Phân khúc RFM
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 text-rose-300 text-sm bg-rose-500/10 border border-rose-400/20 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {tab === 'directory' && (
        <>
          <div className="flex flex-wrap gap-2 mb-4">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void loadList()}
              placeholder="Tìm SĐT / tên..."
              className="flex-1 min-w-[180px] rounded-xl bg-slate-900 border border-white/10 px-3 py-2.5 text-white"
            />
            <button
              onClick={() => void loadList()}
              className="rounded-xl bg-indigo-500 px-4 py-2.5 font-medium"
            >
              Tìm
            </button>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 mb-6">
            <h2 className="text-sm font-semibold text-slate-300 mb-2">Thêm khách nhanh</h2>
            <div className="flex flex-wrap gap-2">
              <input
                value={newPhone}
                onChange={(e) => setNewPhone(e.target.value)}
                placeholder="SĐT"
                className="rounded-lg bg-slate-950 border border-white/10 px-3 py-2 text-white"
              />
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Tên"
                className="rounded-lg bg-slate-950 border border-white/10 px-3 py-2 text-white"
              />
              <button
                onClick={() => void createCustomer()}
                className="rounded-lg bg-emerald-600 px-4 py-2 font-medium"
              >
                Tạo KH
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-white/5 text-slate-400">
                <tr>
                  <th className="text-left p-3">Tên</th>
                  <th className="text-left p-3">SĐT</th>
                  <th className="text-left p-3">Ghi chú</th>
                  <th className="p-3" />
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr>
                    <td colSpan={4} className="p-4 text-slate-500">
                      Đang tải...
                    </td>
                  </tr>
                )}
                {!loading &&
                  list.map((c) => (
                    <tr key={c.id} className="border-t border-white/5 hover:bg-white/5">
                      <td className="p-3 text-white font-medium">{c.name || '—'}</td>
                      <td className="p-3 text-slate-300">{c.phone}</td>
                      <td className="p-3 text-slate-500 truncate max-w-[200px]">{c.notes || '—'}</td>
                      <td className="p-3 text-right space-x-2 whitespace-nowrap">
                        <button
                          onClick={() => openCrmProfile(c.id)}
                          className="text-indigo-300 hover:underline"
                        >
                          Hồ sơ
                        </button>
                        <button
                          onClick={() => sellToCustomer(c)}
                          className="text-emerald-300 hover:underline"
                        >
                          → POS
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'rfm' && (
        <div className="rounded-2xl border border-white/10 overflow-hidden">
          <div className="p-3 border-b border-white/10 flex justify-between">
            <span className="text-slate-300 text-sm">Phân khúc theo recency / frequency / monetary</span>
            <button onClick={() => void loadRfm()} className="text-indigo-300 text-sm">
              Làm mới
            </button>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-slate-400">
              <tr>
                <th className="text-left p-3">KH</th>
                <th className="text-left p-3">Segment</th>
                <th className="text-right p-3">F</th>
                <th className="text-right p-3">M</th>
                <th className="text-right p-3">R (ngày)</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {rfm.map((r) => (
                <tr key={r.customer_id} className="border-t border-white/5">
                  <td className="p-3 text-white">
                    {r.name || '—'}
                    <div className="text-xs text-slate-500">{r.phone}</div>
                  </td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-200 text-xs">
                      {r.segment}
                    </span>
                  </td>
                  <td className="p-3 text-right text-slate-300">{r.frequency}</td>
                  <td className="p-3 text-right text-slate-300">{money(r.monetary)}</td>
                  <td className="p-3 text-right text-slate-300">{r.recency_days}</td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => openCrmProfile(r.customer_id)}
                      className="text-indigo-300 text-xs hover:underline"
                    >
                      Mở
                    </button>
                  </td>
                </tr>
              ))}
              {!rfm.length && !loading && (
                <tr>
                  <td colSpan={6} className="p-6 text-center text-slate-500">
                    Chưa có dữ liệu RFM (cần đơn paid gắn KH)
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
