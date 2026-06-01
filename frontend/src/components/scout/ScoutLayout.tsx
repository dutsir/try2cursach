import { useEffect, useState, type ReactNode } from 'react'
import { Outlet } from 'react-router-dom'
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

interface ScoutLayoutProps {
  user?: User | null
  children?: ReactNode
  onLogout?: () => void
}

export function ScoutLayout({ user, children, onLogout }: ScoutLayoutProps) {
  const [modalOpen, setModalOpen] = useState(false)
  const compareCount = useCompareStore(s => s.ids.length)

  useEffect(() => {
    document.body.classList.add('scout-theme')
    return () => {
      document.body.classList.remove('scout-theme')
    }
  }, [])

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
    <div className="min-h-screen bg-scout-bg text-scout-text font-sans">
      <DashNav
        user={user}
        unreadCount={unreadCount}
        onAddProduct={() => setModalOpen(true)}
        onLogout={onLogout}
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
        <main className="px-6 lg:px-10 py-8 lg:pb-20 border-l border-scout-subtle min-h-[800px]">
          {children ?? <Outlet />}
        </main>
      </div>
      {modalOpen && <AddProductModal onClose={() => setModalOpen(false)} />}
    </div>
  )
}
