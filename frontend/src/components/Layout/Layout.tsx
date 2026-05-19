import type { ReactNode } from 'react'
import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import type { User } from '@/types'

interface LayoutProps {
  children?: ReactNode
  user?: User | null
  onLogout?: () => void
}

export function Layout({ children, user, onLogout }: LayoutProps) {
  return (
    <div className="min-h-screen bg-steam-bg text-steam-text">
      <Header user={user} onLogout={onLogout} />
      <main className="mx-auto max-w-7xl px-4 py-6">
        {children || <Outlet />}
      </main>
    </div>
  )
}
