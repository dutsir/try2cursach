import { NavLink } from 'react-router-dom'
import {
  Home,
  Layers,
  Wrench,
  GitCompare,
  Star,
  Bell as BellIcon,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  count?: number
  end?: boolean
}

interface DashSidebarProps {
  productsCount?: number
  wishlistCount?: number
  compareCount?: number
  notificationsCount?: number
  planUsed?: number
  planLimit?: number
}

export function DashSidebar({
  productsCount = 0,
  wishlistCount = 0,
  compareCount = 0,
  notificationsCount = 0,
  planUsed = 0,
  planLimit = 10,
}: DashSidebarProps) {
  const items: NavItem[] = [
    { to: '/',              label: 'Главная',     icon: Home,       count: productsCount, end: true },
    { to: '/catalog',       label: 'Каталог',     icon: Layers },
    { to: '/builder',       label: 'Сборка ПК',   icon: Wrench },
    { to: '/compare',       label: 'Сравнение',   icon: GitCompare, count: compareCount || undefined },
    { to: '/wishlist',      label: 'Вишлист',     icon: Star,       count: wishlistCount || undefined },
    { to: '/notifications', label: 'Уведомления', icon: BellIcon,   count: notificationsCount || undefined },
  ]

  const planPct = planLimit > 0 ? Math.min(100, (planUsed / planLimit) * 100) : 0
  const exceeded = planUsed > planLimit

  return (
    <aside className="bg-scout-bg p-4">
      <div className="px-3 scout-caption">shelf</div>
      <nav className="mt-2 flex flex-col gap-0.5">
        {items.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `group flex items-center gap-2.5 px-3 py-2 rounded-scout text-[13px] transition-colors ${
                isActive
                  ? 'bg-scout-subtle text-scout-text'
                  : 'text-scout-muted hover:bg-scout-subtle/60 hover:text-scout-text'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <item.icon
                  size={14}
                  className={`shrink-0 ${isActive ? 'text-scout-accent' : 'text-scout-dim group-hover:text-scout-muted'}`}
                />
                <span className="flex-1">{item.label}</span>
                {item.count != null && (
                  <span className="text-[11px] text-scout-dim scout-tabnums">{item.count}</span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-10 p-4 bg-scout-elevated border border-scout-subtle rounded-scout-lg">
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-scout-dim uppercase tracking-[0.1em]">free plan</span>
          <button className="text-[11px] text-scout-accent hover:text-scout-accent-hover transition-colors">
            upgrade →
          </button>
        </div>
        <div className="mt-3 text-[13px] text-scout-text scout-tabnums">
          {planUsed} / {planLimit} товаров
        </div>
        <div className="mt-2 h-1 bg-scout-subtle rounded-full overflow-hidden">
          <div
            className="h-full transition-all"
            style={{
              width: `${planPct}%`,
              background: exceeded ? 'var(--color-danger)' : 'var(--color-accent)',
            }}
          />
        </div>
        <div className="mt-2 text-[11px] text-scout-muted">
          {exceeded
            ? 'лимит превышен. некоторые товары не парсятся.'
            : `осталось ${Math.max(0, planLimit - planUsed)} слотов`}
        </div>
      </div>
    </aside>
  )
}
