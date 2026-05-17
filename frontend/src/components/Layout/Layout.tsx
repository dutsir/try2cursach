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
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900">
      {/* Ambient blobs */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/4 h-96 w-96 rounded-full bg-brand-600/20 blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 h-96 w-96 rounded-full bg-purple-600/15 blur-[120px]" />
      </div>

      <Header user={user} onLogout={onLogout} />

      <main className="relative mx-auto max-w-7xl px-4 py-8">
        {children || <Outlet />}
      </main>
    </div>
  )
}
