import { LoginPage } from './components/LoginPage'
import { PosApp } from './components/PosApp'
import { useAuth } from './store/auth'

export default function App() {
  const token = useAuth((s) => s.token)
  const storeId = useAuth((s) => s.storeId)

  if (!token || !storeId) {
    return <LoginPage />
  }
  return <PosApp />
}
