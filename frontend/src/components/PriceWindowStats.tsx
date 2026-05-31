import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { productsApi } from '@/api/products'
import { formatPrice, formatDate, cn } from '@/lib/utils'
import type { PriceStats, PriceWindow, PriceHistory } from '@/types'

interface Props {
  productId: number
  stats?: PriceStats
  window: PriceWindow
}

const WINDOW_DAYS: Record<PriceWindow, number | null> = {
  '7d': 7,
  '30d': 30,
  'all': null,
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

export function PriceWindowStats({ productId, stats, window }: Props) {
  const w = useMemo(() => {
    if (!stats) return null
    if (window === '7d') return stats.window_7d
    if (window === '30d') return stats.window_30d
    return stats.all_time
  }, [stats, window])

  // Для bar-chart дневных средних берём ту же price_history что и основной график
  const { data } = useQuery({
    queryKey: ['price-history', productId],
    queryFn: () => productsApi.priceHistory(productId),
  })

  const dailyBars = useMemo(() => {
    if (!data?.length) return []
    const days = WINDOW_DAYS[window]
    let pool: PriceHistory[] = data
    if (days !== null) {
      const cutoff = new Date()
      cutoff.setDate(cutoff.getDate() - days + 1)
      cutoff.setHours(0, 0, 0, 0)
      pool = data.filter(d => new Date(d.timestamp) >= cutoff)
    }
    // средняя по дню (по всем источникам)
    const byDay = new Map<string, number[]>()
    for (const p of pool) {
      const k = p.timestamp.slice(0, 10)
      if (!byDay.has(k)) byDay.set(k, [])
      byDay.get(k)!.push(p.price)
    }
    return [...byDay.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([iso, prices]) => ({
        iso,
        date: formatDate(iso),
        avg: Math.round(prices.reduce((s, x) => s + x, 0) / prices.length),
      }))
  }, [data, window])

  const avg = w && 'avg' in w ? w.avg ?? null : null
  const minPriceForChart = dailyBars.length ? Math.min(...dailyBars.map(d => d.avg)) : 0
  const maxPriceForChart = dailyBars.length ? Math.max(...dailyBars.map(d => d.avg)) : 0

  return (
    <div className="space-y-4">
      {/* Мини-карточки */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Текущая"
          value={stats?.current != null ? formatPrice(stats.current) : '—'}
          caption={stats?.is_min_all_time ? 'минимум за всё время' : stats?.is_min_30d ? 'минимум за 30 дней' : undefined}
          tone={stats?.is_min_all_time ? 'good' : 'default'}
        />
        <StatCard
          label={avg != null ? 'Средняя' : 'Средняя'}
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

      {/* Bar-chart дневных средних */}
      {dailyBars.length > 0 && (
        <div>
          <div className="mb-2 flex items-baseline justify-between">
            <h3 className="text-sm font-medium text-scout-muted">Средняя цена по дням</h3>
            <span className="text-xs text-scout-dim">{dailyBars.length} {pluralize(dailyBars.length, 'день', 'дня', 'дней')}</span>
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={dailyBars} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[Math.max(0, minPriceForChart * 0.97), maxPriceForChart * 1.03]}
                tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={v => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)}
                width={40}
              />
              <Tooltip
                cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                content={({ active, payload, label }) => {
                  if (!active || !payload?.length) return null
                  return (
                    <div className="rounded-scout border border-scout-border bg-scout-elevated px-3 py-2 text-xs shadow">
                      <div className="text-scout-muted">{label}</div>
                      <div className="font-semibold text-scout-text scout-tabnums">{formatPrice(payload[0].value as number)}</div>
                    </div>
                  )
                }}
              />
              <Bar dataKey="avg" radius={[4, 4, 0, 0]}>
                {dailyBars.map((d, i) => {
                  const isMin = w?.min != null && d.avg === w.min
                  const isMax = w?.max != null && d.avg === w.max
                  let fill = '#A855F7'
                  if (isMax) fill = '#ef4444'
                  else if (isMin) fill = '#10B981'
                  return <Cell key={i} fill={fill} />
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
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
