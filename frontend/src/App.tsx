import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { ScoutLayout } from '@/components/scout'
import { ToastProvider } from '@/components/ui/Toast'
import { PageSpinner } from '@/components/ui/Spinner'
import { initAuth } from '@/hooks/useAuth'
import { api } from '@/api/client'
import { useCompareStore } from '@/store/compare'
import { useBuildStore } from '@/store/build'
import type { User } from '@/types'

const Dashboard     = lazy(() => import('@/pages/Dashboard'))
const Catalog       = lazy(() => import('@/pages/Catalog'))
const Compare       = lazy(() => import('@/pages/Compare'))
const Builder       = lazy(() => import('@/pages/Builder'))
const Wishlist      = lazy(() => import('@/pages/Wishlist'))
const Subscriptions = lazy(() => import('@/pages/Subscriptions'))
const ProductDetail = lazy(() => import('@/pages/ProductDetail'))
const Notifications = lazy(() => import('@/pages/Notifications'))
const Settings      = lazy(() => import('@/pages/Settings'))
const Login         = lazy(() => import('@/pages/Login'))
const Register      = lazy(() => import('@/pages/Register'))
const VerifyEmail   = lazy(() => import('@/pages/VerifyEmail'))
const ForgotPassword = lazy(() => import('@/pages/ForgotPassword'))
const ResetPassword  = lazy(() => import('@/pages/ResetPassword'))

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

  const prevUserIdRef = useRef<number | null | undefined>(undefined)

  // Привязываем локальные списки (сравнение, сборка) к текущему юзеру.
  // При смене аккаунта или выходе чужие списки очищаются.
  // Ждём окончания initAuth: на старте user=null (ещё не загружен), и без этой
  // защиты ensureOwner(null) затирал бы сохранённый список при каждой перезагрузке.
  useEffect(() => {
    if (loading) return
    const id = user?.id ?? null
    useCompareStore.getState().ensureOwner(id)
    useBuildStore.getState().ensureOwner(id)

    // Сброс React Query кэша при реальной смене аккаунта (вход/выход/другой юзер).
    // Иначе подписки/вишлист/уведомления предыдущего юзера остаются в кэше SPA
    // и показываются под другим аккаунтом без перезагрузки страницы.
    const changed = prevUserIdRef.current !== id
    if (prevUserIdRef.current !== undefined && changed) {
      qc.clear()
    }
    // Подтягиваем серверную сборку при входе/смене аккаунта (после ensureOwner,
    // которая для нового юзера уже очистила чужие локальные слоты).
    if (changed && id !== null) {
      useBuildStore.getState().hydrateFromServer()
    }
    prevUserIdRef.current = id
  }, [user, loading])

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
              <Route path="/login"        element={user ? <Navigate to="/" /> : <Login    onLogin={setUser} />} />
              <Route path="/register"     element={user ? <Navigate to="/" /> : <Register onRegister={setUser} />} />
              <Route path="/verify-email" element={<VerifyEmail />} />
              <Route path="/forgot-password" element={user ? <Navigate to="/" /> : <ForgotPassword />} />
              <Route path="/reset-password"  element={<ResetPassword />} />

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
                <Route path="/subscriptions" element={<Subscriptions />} />
                <Route path="/products/:id"  element={<ProductDetail />} />
                <Route path="/notifications" element={<Notifications />} />
                <Route path="/settings"      element={<Settings user={user} onUserChange={setUser} />} />
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
