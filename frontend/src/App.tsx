import { lazy, Suspense, useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { ScoutLayout } from '@/components/scout'
import { ToastProvider } from '@/components/ui/Toast'
import { PageSpinner } from '@/components/ui/Spinner'
import { initAuth } from '@/hooks/useAuth'
import { api } from '@/api/client'
import type { User } from '@/types'

const Dashboard     = lazy(() => import('@/pages/Dashboard'))
const Catalog       = lazy(() => import('@/pages/Catalog'))
const Compare       = lazy(() => import('@/pages/Compare'))
const Builder       = lazy(() => import('@/pages/Builder'))
const Wishlist      = lazy(() => import('@/pages/Wishlist'))
const ProductDetail = lazy(() => import('@/pages/ProductDetail'))
const Notifications = lazy(() => import('@/pages/Notifications'))
const Login         = lazy(() => import('@/pages/Login'))
const Register      = lazy(() => import('@/pages/Register'))

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

function ProtectedRoute({ user, children }: { user: User | null; children: React.ReactNode }) {
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    initAuth().then(u => {
      setUser(u)
      setLoading(false)
    })
  }, [])

  async function handleLogout() {
    try {
      await api.post('/api/auth/logout/', {})
    } catch (e) {
      console.error('Logout error:', e)
    }
    setUser(null)
  }

  if (loading) return <PageSpinner />

  return (
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <BrowserRouter>
          <Suspense fallback={<PageSpinner />}>
            <Routes>
              {/* Auth routes — no layout */}
              <Route path="/login"    element={user ? <Navigate to="/" /> : <Login    onLogin={setUser} />} />
              <Route path="/register" element={user ? <Navigate to="/" /> : <Register onRegister={setUser} />} />

              {/* Protected routes — all under Scout layout */}
              <Route element={
                <ProtectedRoute user={user}>
                  <ScoutLayout user={user} onLogout={handleLogout} />
                </ProtectedRoute>
              }>
                <Route path="/"              element={<Dashboard />} />
                <Route path="/catalog"       element={<Catalog />} />
                <Route path="/compare"       element={<Compare />} />
                <Route path="/builder"       element={<Builder />} />
                <Route path="/wishlist"      element={<Wishlist />} />
                <Route path="/products/:id"  element={<ProductDetail />} />
                <Route path="/notifications" element={<Notifications />} />
              </Route>

              {/* Fallback redirects */}
              <Route path="*" element={<Navigate to={user ? '/' : '/login'} replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </ToastProvider>
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  )
}
