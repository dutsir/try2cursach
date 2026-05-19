import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { notificationsApi } from '@/api/subscriptions'
import { cn } from '@/lib/utils'
import type { User as UserType } from '@/types'

const NAV = [
  { to: '/',          label: 'КАТАЛОГ' },
  { to: '/wishlist',  label: 'ВИШЛИСТ' },
  { to: '/anomalies', label: 'АНОМАЛИИ' },
]

interface HeaderProps {
  user?: UserType | null
  onLogout?: () => void
}

export function Header({ user, onLogout }: HeaderProps) {
  const { pathname } = useLocation()
  const [profileOpen, setProfileOpen] = useState(false)

  const { data: notifs } = useQuery({
    queryKey: ['notifications'],
    queryFn: notificationsApi.list,
    refetchInterval: 60_000,
  })
  const unreadCount = notifs?.count ?? 0

  return (
    <header className="sticky top-0 z-50 bg-steam-darker border-b border-steam-border shadow-[0_2px_0_rgba(0,0,0,0.3)]">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
        <Link to="/" className="flex items-center gap-2 font-bold text-white tracking-wide">
          <span className="text-steam-blue text-lg">PRICE</span>
          <span className="text-white text-lg">WATCH</span>
        </Link>

        <nav className="flex items-center gap-1">
          {NAV.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              className={cn(
                'px-3 py-1.5 text-xs font-medium tracking-wider transition-colors duration-100',
                pathname === to
                  ? 'text-white'
                  : 'text-steam-muted hover:text-steam-light',
              )}
            >
              {label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <Link
            to="/notifications"
            className="relative px-3 py-1.5 text-xs font-medium tracking-wider text-steam-muted hover:text-steam-light transition-colors"
          >
            УВЕДОМЛЕНИЯ
            {unreadCount > 0 && (
              <span className="ml-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-steam bg-steam-blue px-1 text-[10px] font-bold text-steam-darker">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </Link>

          {user && (
            <div className="relative">
              <button
                onClick={() => setProfileOpen(!profileOpen)}
                className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium tracking-wider text-steam-light hover:text-white transition-colors"
              >
                <span className="flex h-6 w-6 items-center justify-center bg-steam-border text-[11px] font-bold uppercase text-steam-light">
                  {user.first_name?.charAt(0) || user.username?.charAt(0) || 'U'}
                </span>
                <span className="uppercase">{user.first_name || user.username}</span>
              </button>

              {profileOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-steam-darker border border-steam-border rounded-steam shadow-lg">
                  <div className="border-b border-steam-border px-4 py-3">
                    <p className="text-sm font-medium text-white">{user.first_name || user.username}</p>
                    <p className="text-xs text-steam-muted">{user.email}</p>
                  </div>
                  <button
                    onClick={() => { setProfileOpen(false); onLogout?.() }}
                    className="w-full px-4 py-2.5 text-left text-xs font-medium tracking-wider text-steam-muted hover:bg-steam-panel hover:text-white transition-colors"
                  >
                    ВЫХОД
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
