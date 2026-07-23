import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'

export type Lang = 'vi' | 'en'

const dict = {
  vi: {
    pos: 'POS',
    crm: 'CRM',
    inventory: 'Kho',
    reports: 'Báo cáo',
    logout: 'Thoát',
    online: 'Online',
    offline: 'Offline',
    search: 'Tìm',
    pay: 'Thanh toán',
    customer: 'Khách hàng',
    tasks: 'Công việc',
    lowStock: 'Tồn thấp',
    transfer: 'Chuyển kho',
    stocktake: 'Kiểm kê',
    exportCsv: 'Xuất CSV',
    language: 'Ngôn ngữ',
    ops: 'Ops',
    openShift: 'Mở ca',
    closeShift: 'Đóng ca',
    backup: 'Backup',
  },
  en: {
    pos: 'POS',
    crm: 'CRM',
    inventory: 'Stock',
    reports: 'Reports',
    logout: 'Logout',
    online: 'Online',
    offline: 'Offline',
    search: 'Search',
    pay: 'Pay',
    customer: 'Customer',
    tasks: 'Tasks',
    lowStock: 'Low stock',
    transfer: 'Transfer',
    stocktake: 'Stocktake',
    exportCsv: 'Export CSV',
    language: 'Language',
    ops: 'Ops',
    openShift: 'Open shift',
    closeShift: 'Close shift',
    backup: 'Backup',
  },
} as const

export type I18nKey = keyof (typeof dict)['vi']

type I18nCtx = {
  lang: Lang
  setLang: (l: Lang) => void
  t: (k: I18nKey) => string
}

const Ctx = createContext<I18nCtx | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const saved = localStorage.getItem('pos_lang')
    return saved === 'en' || saved === 'vi' ? saved : 'vi'
  })
  const setLang = (l: Lang) => {
    localStorage.setItem('pos_lang', l)
    setLangState(l)
    document.documentElement.lang = l
  }
  const value = useMemo<I18nCtx>(
    () => ({
      lang,
      setLang,
      t: (k) => dict[lang][k] ?? k,
    }),
    [lang],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useI18n() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useI18n outside provider')
  return ctx
}
