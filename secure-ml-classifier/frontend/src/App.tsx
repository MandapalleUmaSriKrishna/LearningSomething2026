import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { useAuth } from './lib/auth'
import { Spinner } from './components/ui'
import Account from './pages/Account'
import Admin from './pages/Admin'
import Dashboard from './pages/Dashboard'
import DatasetDetail from './pages/DatasetDetail'
import Datasets from './pages/Datasets'
import Login from './pages/Login'
import RunDetail from './pages/RunDetail'
import Runs from './pages/Runs'

export default function App() {
  const { user, loading } = useAuth()

  if (loading) return <Spinner label="Restoring session…" />
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="datasets" element={<Datasets />} />
        <Route path="datasets/:datasetId" element={<DatasetDetail />} />
        <Route path="runs" element={<Runs />} />
        <Route path="runs/:runId" element={<RunDetail />} />
        <Route path="account" element={<Account />} />
        {user.role === 'admin' && <Route path="admin" element={<Admin />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
