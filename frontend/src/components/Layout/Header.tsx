import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Sun, Moon, Bell, TrendingUp, LayoutGrid, BookMarked, LogOut, User } from 'lucide-react'
import { useTheme } from '@/hooks/useTheme'
import { useQuery } from '@tanstack/react-query'
import { notificationsApi } from '@/api/subscriptions'
import { cn } from '@/lib/utils'
import type { User as UserType } from '@/types'

const NAV = [
  { to: '/',             label: 'Каталог',    icon: LayoutGrid },
  { to: '/wishlist',     label: 'Вишлист',    icon: BookMarked },
  { to: '/anomalies',    label: 'Аномалии',   icon: TrendingUp },
]

interface HeaderProps {
  user?: UserType | null
  onLogout?: () => void
}

export function Header({ user, onLogout }: HeaderProps) {
  const { theme, toggle } = useTheme()
  const { pathname } = useLocation()
  const [profileOpen, setProfileOpen] = useState(false)

  const { data: notifs } = useQuery({
    queryKey: ['notifications'],
    queryFn: notificationsApi.list,
    refetchInterval: 60_000,
  })
  const unreadCount = notifs?.count ?? 0

  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-slate-950/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 font-bold text-white">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-purple-600 text-sm">
            P
          </span>
          <span className="hidden sm:block">PriceWatch</span>
        </Link>

        {/* Nav */}
        <nav className="flex items-center gap-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className={cn(
                'flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-all duration-200',
                pathname === to
                  ? 'bg-brand-600/30 text-brand-300'
                  : 'text-white/60 hover:bg-white/10 hover:text-white',
              )}
            >
              <Icon size={16} />
              <span className="hidden sm:block">{label}</span>
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {/* Notifications */}
          <Link
            to="/notifications"
            className="relative rounded-xl p-2 text-white/60 transition hover:bg-white/10 hover:text-white"
          >
            <Bell size={18} />
            {unreadCount > 0 && (
              <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-brand-500 text-[10px] font-bold text-white">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </Link>

          {/* Theme toggle */}
          <button
            onClick={toggle}
            className="rounded-xl p-2 text-white/60 transition hover:bg-white/10 hover:text-white"
            aria-label="Переключить тему"
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          {/* Profile menu */}
          {user && (
            <div className="relative">
              <button
                onClick={() => setProfileOpen(!profileOpen)}
                className="flex items-center gap-2 rounded-xl p-2 text-white/60 transition hover:bg-white/10 hover:text-white"
              >
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-600">
                  <span className="text-xs font-bold uppercase">
                    {user.first_name?.charAt(0) || user.username?.charAt(0) || 'U'}
                  </span>
                </div>
              </button>

              {profileOpen && (
                <div className="absolute right-0 mt-2 w-48 rounded-xl border border-white/10 bg-slate-900/95 shadow-xl backdrop-blur-xl">
                  <div className="px-4 py-3 border-b border-white/10">
                    <p className="text-sm font-medium text-white">{user.first_name || user.username}</p>
                    <p className="text-xs text-white/40">{user.email}</p>
                  </div>
                  <button
                    onClick={() => {
                      setProfileOpen(false)
                      onLogout?.()
                    }}
                    className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-white/60 transition hover:bg-white/10 hover:text-white"
                  >
                    <LogOut size={15} />
                    Выход
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
