import { create } from 'zustand'
import type { Customer } from '../lib/api'

export type AppModule = 'pos' | 'crm' | 'eod' | 'inventory'

type AppState = {
  module: AppModule
  /** Customer selected in CRM to sell on POS */
  posCustomer: Customer | null
  /** CRM profile to open */
  crmCustomerId: string | null
  setModule: (m: AppModule) => void
  openCrmProfile: (customerId: string) => void
  clearCrmProfile: () => void
  sellToCustomer: (c: Customer) => void
  clearPosCustomer: () => void
}

export const useAppNav = create<AppState>((set) => ({
  module: 'pos',
  posCustomer: null,
  crmCustomerId: null,
  setModule: (module) => set({ module }),
  openCrmProfile: (customerId) => set({ module: 'crm', crmCustomerId: customerId }),
  clearCrmProfile: () => set({ crmCustomerId: null }),
  sellToCustomer: (c) => set({ module: 'pos', posCustomer: c }),
  clearPosCustomer: () => set({ posCustomer: null }),
}))
