import { lazy, Suspense, useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { Layout } from '@/components/Layout/Layout'
import { ToastProvider } from '@/components/ui/Toast'
import { PageSpinner } from '@/components/ui/Spinner'
import { initAuth } from '@/hooks/useAuth'
import type { User } from '@/types'

const Catalog       = lazy(() => import('@/pages/Catalog'))
const Wishlist      = lazy(() => import('@/pages/Wishlist'))
const ProductDetail = lazy(() => import('@/pages/ProductDetail'))
const Notifications = lazy(() => import('@/pages/Notifications'))
const Anomalies     = lazy(() => import('@/pages/Anomalies'))
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

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    initAuth().then(u => {
      setUser(u)
      setLoading(false)
    })
  }, [])

  if (loading) return <PageSpinner />

  return (
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <BrowserRouter>
          <Suspense fallback={<PageSpinner />}>
            <Routes>
              {/* Auth routes */}
              {!user && (
                <>
                  <Route path="/login" element={<Login />} />
                  <Route path="/register" element={<Register />} />
                </>
              )}

              {/* Protected routes with layout */}
              {user && (
                <Route element={<Layout user={user} onLogout={() => setUser(null)} />}>
                  <Route path="/"                  element={<Catalog />} />
                  <Route path="/wishlist"          element={<Wishlist />} />
                  <Route path="/products/:id"      element={<ProductDetail />} />
                  <Route path="/notifications"     element={<Notifications />} />
                  <Route path="/anomalies"         element={<Anomalies />} />
                </Route>
              )}

              {/* Fallback redirects */}
              <Route path="*" element={<Navigate to={user ? "/" : "/login"} replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </ToastProvider>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
