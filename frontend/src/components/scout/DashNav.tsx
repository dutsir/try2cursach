import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bell, LogOut, Menu, ScanSearch } from 'lucide-react'
import type { User } from '@/types'

interface DashNavProps {
  user?: User | null
  unreadCount?: number
  onAddProduct?: () => void
  onLogout?: () => void
  onOpenNav?: () => void
}

export function DashNav({ user, unreadCount = 0, onAddProduct, onLogout, onOpenNav }: DashNavProps) {
  const navigate = useNavigate()
  const [profileOpen, setProfileOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)

  const initial = user?.first_name?.charAt(0) || user?.username?.charAt(0) || 'A'

  useEffect(() => {
    if (!profileOpen) return
    function handleClick(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [profileOpen])

  return (
    <header className="sticky top-0 z-30 h-16 flex items-center justify-between px-6 border-b border-scout-subtle bg-scout-bg">
      <div className="flex items-center gap-4 md:gap-8">
        <button
          onClick={onOpenNav}
          className="lg:hidden w-9 h-9 -ml-1 rounded-scout text-scout-muted hover:bg-scout-subtle hover:text-scout-text transition-colors flex items-center justify-center shrink-0"
          aria-label="Меню"
        >
          <Menu size={18} />
        </button>
        <Link to="/" className="flex items-center gap-2.5">
          <div className="relative w-[22px] h-[22px] rounded-[5px] bg-scout-bg border-[1.5px] border-scout-accent">
            <span className="absolute -top-[3px] left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-scout-accent" />
          </div>
          <span className="font-display text-[17px] font-bold tracking-[-0.02em] text-scout-text lowercase">
            scout
          </span>
        </Link>
      </div>

      <div className="flex items-center gap-3 md:gap-4">
        <button onClick={onAddProduct} className="scout-btn-primary text-[13px]">
          <ScanSearch size={14} strokeWidth={2.5} />
          <span className="hidden sm:inline">найти товар</span>
        </button>

        <button
          onClick={() => navigate('/notifications')}
          className="relative w-9 h-9 rounded-scout bg-transparent border border-scout-subtle text-scout-muted hover:bg-scout-subtle hover:text-scout-text transition-colors flex items-center justify-center"
          title="Уведомления"
        >
          <Bell size={15} />
          {unreadCount > 0 && (
            <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-scout-danger" />
          )}
        </button>

        <div className="relative" ref={profileRef}>
          <button
            onClick={() => setProfileOpen(o => !o)}
            className="w-8 h-8 rounded-full bg-scout-subtle border border-scout-border flex items-center justify-center text-[12px] font-semibold text-scout-muted uppercase hover:text-scout-text hover:border-scout-accent/50 transition-colors"
            aria-label="Профиль"
          >
            {initial}
          </button>

          {profileOpen && user && (
            <div className="absolute right-0 mt-2 w-60 bg-scout-elevated border border-scout-border rounded-scout-lg shadow-[0_12px_40px_rgba(0,0,0,0.5)] overflow-hidden">
              <div className="px-4 py-3 border-b border-scout-subtle">
                <div className="text-[13px] font-semibold text-scout-text truncate">
                  {user.first_name || user.username}
                </div>
                <div className="text-[11px] text-scout-muted truncate">{user.email}</div>
              </div>
              <button
                onClick={() => {
                  setProfileOpen(false)
                  onLogout?.()
                }}
                className="w-full px-4 py-2.5 text-left text-[12px] uppercase tracking-[0.08em] text-scout-muted hover:bg-scout-subtle hover:text-scout-danger transition-colors flex items-center gap-2"
              >
                <LogOut size={12} />
                Выход
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
