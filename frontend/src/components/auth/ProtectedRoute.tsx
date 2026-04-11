import { useEffect } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import AppShell from '@/components/layout/AppShell'

function LoadingSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--void)' }}>
      <div
        className="w-8 h-8 rounded-full border-2 border-transparent"
        style={{
          borderTopColor: 'var(--forge)',
          animation: 'spin 1s linear infinite',
        }}
      />
    </div>
  )
}

export default function ProtectedRoute({ noShell = false }: { noShell?: boolean }) {
  const { isLoading, isAuthenticated, initialize } = useAuthStore()
  const location = useLocation()

  useEffect(() => {
    initialize()
  }, [initialize])

  if (isLoading) return <LoadingSpinner />

  if (!isAuthenticated) {
    const redirect = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?redirect=${redirect}`} replace />
  }

  if (noShell) return <Outlet />

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  )
}
