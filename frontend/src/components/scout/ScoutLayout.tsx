import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { DashNav } from './DashNav'
import { DashSidebar } from './DashSidebar'
import { AddProductModal } from './AddProductModal'
import { EmailVerifyBanner } from '@/components/EmailVerifyBanner'
import { notificationsApi, subscriptionsApi } from '@/api/subscriptions'
import { productsApi } from '@/api/products'
import { wishlistApi } from '@/api/wishlist'
import { useCompareStore } from '@/store/compare'
import type { User } from '@/types'

interface ScoutLayoutContextValue {
  openAddProduct: () => void
}

const ScoutLayoutContext = createContext<ScoutLayoutContextValue | null>(null)

export function useScoutLayout(): ScoutLayoutContextValue {
  const ctx = useContext(ScoutLayoutContext)
  if (!ctx) {
    throw new Error('useScoutLayout must be used within ScoutLayout')
  }
  return ctx
}

interface ScoutLayoutProps {
  user?: User | null
  children?: ReactNode
  onLogout?: () => void
}

export function ScoutLayout({ user, children, onLogout }: ScoutLayoutProps) {
  const [modalOpen, setModalOpen] = useState(false)
  const openAddProduct = useCallback(() => setModalOpen(true), [])
  const [navOpen, setNavOpen] = useState(false)
  const compareCount = useCompareStore(s => s.ids.length)
  const location = useLocation()

  useEffect(() => {
    document.body.classList.add('scout-theme')
    return () => {
      document.body.classList.remove('scout-theme')
    }
  }, [])

  // Закрываем мобильное меню при переходе на другую страницу.
  useEffect(() => {
    setNavOpen(false)
  }, [location.pathname])

  // Горячая клавиша из EmptyDash: ⌘N / Ctrl+N.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault()
        openAddProduct()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [openAddProduct])

  // Блокируем скролл фона, пока открыт мобильный drawer.
  useEffect(() => {
    if (!navOpen) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [navOpen])

  const { data: notifs } = useQuery({
    queryKey: ['notifications'],
    queryFn: notificationsApi.list,
    refetchInterval: 60_000,
  })
  const unreadCount = notifs?.results.filter(n => !n.is_read).length ?? 0

  const { data: productsResp } = useQuery({
    queryKey: ['products', { page_size: 1 }],
    queryFn: () => productsApi.list({ page_size: 1 }),
    staleTime: 60_000,
  })
  const productsCount = productsResp?.count ?? 0

  const { data: wishlist } = useQuery({
    queryKey: ['wishlist'],
    queryFn: wishlistApi.get,
    staleTime: 60_000,
    retry: false,
  })
  const wishlistCount = wishlist?.items?.length ?? 0

  const { data: subs } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: subscriptionsApi.list,
    staleTime: 60_000,
    retry: false,
  })
  const subscriptionsCount = subs?.count ?? subs?.results?.length ?? 0

  return (
    <ScoutLayoutContext.Provider value={{ openAddProduct }}>
    <div className="min-h-screen bg-scout-bg text-scout-text font-sans">
      <DashNav
        user={user}
        unreadCount={unreadCount}
        onAddProduct={openAddProduct}
        onLogout={onLogout}
        onOpenNav={() => setNavOpen(true)}
      />
      {user && <EmailVerifyBanner user={user} />}
      <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] min-h-[calc(100vh-64px)]">
        <div className="hidden lg:block">
          <DashSidebar
            productsCount={productsCount}
            wishlistCount={wishlistCount}
            compareCount={compareCount}
            subscriptionsCount={subscriptionsCount}
            notificationsCount={unreadCount}
          />
        </div>
        <main className="px-4 sm:px-6 lg:px-10 py-6 sm:py-8 lg:pb-20 lg:border-l border-scout-subtle min-h-[800px] overflow-x-hidden">
          {children ?? <Outlet />}
        </main>
      </div>

      {/* Мобильное навигационное меню (drawer) */}
      {navOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-scout-fade"
            onClick={() => setNavOpen(false)}
          />
          <div className="absolute left-0 top-0 h-full w-[260px] max-w-[80vw] bg-scout-bg border-r border-scout-subtle shadow-[0_0_40px_rgba(0,0,0,0.6)] overflow-y-auto animate-scout-slide-in">
            <div className="flex items-center justify-between px-4 h-16 border-b border-scout-subtle">
              <span className="font-display text-[17px] font-bold tracking-[-0.02em] text-scout-text lowercase">
                scout
              </span>
              <button
                onClick={() => setNavOpen(false)}
                className="w-9 h-9 rounded-scout text-scout-muted hover:bg-scout-subtle hover:text-scout-text transition-colors flex items-center justify-center"
                aria-label="Закрыть меню"
              >
                <X size={18} />
              </button>
            </div>
            <DashSidebar
              productsCount={productsCount}
              wishlistCount={wishlistCount}
              compareCount={compareCount}
              subscriptionsCount={subscriptionsCount}
              notificationsCount={unreadCount}
              onNavigate={() => setNavOpen(false)}
            />
          </div>
        </div>
      )}

      {modalOpen && <AddProductModal onClose={() => setModalOpen(false)} />}
    </div>
    </ScoutLayoutContext.Provider>
  )
}
