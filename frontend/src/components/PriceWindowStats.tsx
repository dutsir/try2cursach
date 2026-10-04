import { useMemo } from 'react'
import { formatPrice, formatDate, cn } from '@/lib/utils'
import type { PriceStats, PriceWindow } from '@/types'

interface Props {
  productId: number
  stats?: PriceStats
  window: PriceWindow
}

interface CardProps {
  label: string
  value: string
  caption?: string
  tone?: 'default' | 'good' | 'bad' | 'neutral'
}

function StatCard({ label, value, caption, tone = 'default' }: CardProps) {
  const toneClass = {
    default: 'text-scout-text',
    good: 'text-scout-success',
    bad: 'text-scout-danger',
    neutral: 'text-scout-accent',
  }[tone]
  return (
    <div className="rounded-scout border border-scout-subtle bg-scout-bg px-4 py-3">
      <div className="scout-caption">{label}</div>
      <div className={cn('mt-1 text-lg font-semibold scout-tabnums', toneClass)}>{value}</div>
      {caption && <div className="mt-0.5 text-xs text-scout-dim">{caption}</div>}
    </div>
  )
}

export function PriceWindowStats({ stats, window }: Props) {
  const w = useMemo(() => {
    if (!stats) return null
    if (window === '7d') return stats.window_7d
    if (window === '30d') return stats.window_30d
    return stats.all_time
  }, [stats, window])

  const avg = w && 'avg' in w ? w.avg ?? null : null

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatCard
        label="Текущая"
        value={stats?.current != null ? formatPrice(stats.current) : '—'}
        caption={stats?.is_min_all_time ? 'минимум за всё время' : stats?.is_min_30d ? 'минимум за 30 дней' : undefined}
        tone={stats?.is_min_all_time ? 'good' : 'default'}
      />
      <StatCard
        label="Средняя"
        value={avg != null ? formatPrice(avg) : '—'}
        caption={w?.points ? `${w.points} ${pluralize(w.points, 'точка', 'точки', 'точек')}` : undefined}
        tone="neutral"
      />
      <StatCard
        label="Минимум"
        value={w?.min != null ? formatPrice(w.min) : '—'}
        caption={w?.min_date ? formatDate(w.min_date) : undefined}
        tone="good"
      />
      <StatCard
        label="Максимум"
        value={w?.max != null ? formatPrice(w.max) : '—'}
        caption={w?.max_date ? formatDate(w.max_date) : undefined}
        tone="bad"
      />
    </div>
  )
}

function pluralize(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}
