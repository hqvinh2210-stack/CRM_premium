import { AppShell } from './components/AppShell'
import { CrmApp } from './components/crm/CrmApp'
import { EodPanel } from './components/EodPanel'
import { InventoryPanel } from './components/InventoryPanel'
import { LoginPage } from './components/LoginPage'
import { PosApp } from './components/PosApp'
import { useAppNav } from './store/app'
import { useAuth } from './store/auth'

export default function App() {
  const token = useAuth((s) => s.token)
  const storeId = useAuth((s) => s.storeId)
  const module = useAppNav((s) => s.module)

  if (!token || !storeId) {
    return <LoginPage />
  }

  return (
    <AppShell>
      {module === 'pos' && <PosApp />}
      {module === 'crm' && <CrmApp />}
      {module === 'inventory' && <InventoryPanel />}
      {module === 'eod' && (
        <div className="h-full overflow-auto">
          <EodPanel />
        </div>
      )}
    </AppShell>
  )
}
