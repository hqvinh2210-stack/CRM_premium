import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '../lib/api'

type StoreInfo = { store_id: string; code: string; name: string; role: string }

type AuthState = {
  token: string | null
  storeId: string | null
  role: string | null
  email: string | null
  stores: StoreInfo[]
  login: (email: string, password: string) => Promise<void>
  selectStore: (storeId: string) => void
  logout: () => void
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      storeId: null,
      role: null,
      email: null,
      stores: [],
      async login(email, password) {
        const data = await api.login(email, password)
        const me = await api.me(data.access_token)
        set({
          token: data.access_token,
          storeId: data.store_id,
          role: data.role,
          email,
          stores: me.stores,
        })
      },
      selectStore(storeId) {
        const s = get().stores.find((x) => x.store_id === storeId)
        set({ storeId, role: s?.role ?? get().role })
      },
      logout() {
        set({ token: null, storeId: null, role: null, email: null, stores: [] })
      },
    }),
    { name: 'pos-auth' },
  ),
)
