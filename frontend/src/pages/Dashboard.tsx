import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import type { LucideIcon } from 'lucide-react'
import {
  Package, Tag, Store, Activity, ArrowRight,
  Cpu, MemoryStick, Monitor, HardDrive, Plug, Box, CircuitBoard,
} from 'lucide-react'
import { dashboardApi } from '@/api/dashboard'
import { DealCard } from '@/components/DealCard'
import { Spinner } from '@/components/ui/Spinner'

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  processory:           Cpu,
  videokarty:           Monitor,
  'materinskie-platy':  CircuitBoard,
  'operativnaya-pamyat': MemoryStick,
  'bloki-pitaniya':     Plug,
  korpusa:              Box,
  'ssd-nakopiteli':     HardDrive,
  'zhestkie-diski-35':  HardDrive,
}

export default function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: dashboardApi.get,
    staleTime: 5 * 60_000,
  })

  if (isLoading) return <div className="flex justify-center py-20"><Spinner /></div>
  if (!data) return null

  return (
    <div className="space-y-8">
      {/* Heading */}
      <div>
        <h1 className="text-2xl font-bold text-white mb-1">Мониторинг цен на комплектующие ПК</h1>
        <p className="text-sm text-steam-muted">DNS · Wildberries · Ситилинк · Ozon</p>
      </div>

      {/* Stats */}
      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard icon={Package}  label="Товаров"     value={data.totals.products} />
        <StatCard icon={Tag}      label="Категорий"   value={data.totals.categories} />
        <StatCard icon={Store}    label="Офферов"     value={data.totals.offers} />
        <StatCard icon={Activity} label="Цен за 24ч"  value={data.totals.price_records_24h} accent />
      </section>

      {/* Top deals */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-bold text-steam-light">🔥 Горячие скидки</h2>
          <Link to="/catalog?ordering=-min_price" className="text-xs uppercase tracking-wider text-steam-blue hover:underline flex items-center gap-1">
            Весь каталог <ArrowRight size={12} />
          </Link>
        </div>
        {data.top_deals.length === 0 ? (
          <div className="text-sm text-steam-muted">Сейчас нет активных скидок</div>
        ) : (
          <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1">
            {data.top_deals.map(d => <DealCard key={d.id} deal={d} />)}
          </div>
        )}
      </section>

      {/* Popular categories */}
      <section>
        <h2 className="text-lg font-bold text-steam-light mb-3">Популярные категории</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {data.popular_categories.map(c => {
            const Icon = CATEGORY_ICONS[c.slug] || Package
            return (
              <Link
                key={c.id}
                to={`/catalog?category=${c.slug}`}
                className="group flex items-center gap-3 rounded-steam border border-steam-border bg-steam-card p-3 transition-colors hover:border-steam-blue/60"
              >
                <Icon size={22} className="text-steam-blue shrink-0" />
                <div className="flex flex-col min-w-0">
                  <span className="text-sm font-medium text-steam-light truncate">{c.name}</span>
                  <span className="text-[10px] uppercase tracking-wider text-steam-muted">{c.count.toLocaleString('ru-RU')} товаров</span>
                </div>
              </Link>
            )
          })}
        </div>
      </section>

      {/* CTA Builder */}
      <section className="rounded-steam border border-steam-blue/40 bg-gradient-to-r from-steam-blue/10 to-transparent p-6">
        <div className="flex flex-col sm:flex-row items-center gap-4">
          <div className="flex-1">
            <h3 className="text-base font-bold text-steam-light mb-1">Собери свой ПК с лучшей ценой</h3>
            <p className="text-sm text-steam-muted">
              Выбирай компоненты, мы найдём лучшую цену в каждом магазине.
            </p>
          </div>
          <Link
            to="/builder"
            className="rounded-steam bg-steam-blue px-5 py-2 text-xs font-bold uppercase tracking-wider text-steam-darker hover:bg-steam-blue/90 transition-colors"
          >
            Начать сборку
          </Link>
        </div>
      </section>
    </div>
  )
}

function StatCard({ icon: Icon, label, value, accent }: {
  icon: LucideIcon
  label: string
  value: number
  accent?: boolean
}) {
  return (
    <div className="rounded-steam border border-steam-border bg-steam-card p-4">
      <div className="flex items-start justify-between">
        <span className="text-[10px] uppercase tracking-wider text-steam-muted">{label}</span>
        <Icon size={16} className={accent ? 'text-steam-green' : 'text-steam-blue'} />
      </div>
      <div className={`mt-2 text-2xl font-bold ${accent ? 'text-steam-green' : 'text-steam-light'}`}>
        {value.toLocaleString('ru-RU')}
      </div>
    </div>
  )
}
