import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, ReferenceDot, Label,
} from 'recharts'
import { productsApi } from '@/api/products'
import { formatPrice, formatDate, SOURCE_COLORS } from '@/lib/utils'
import { PageSpinner } from '@/components/ui/Spinner'
import type { PriceHistory, PriceStats, PriceWindow } from '@/types'

interface PriceChartProps {
  productId: number
  targetPrice?: number
  window?: PriceWindow      // '7d' | '30d' | 'all'  (по умолчанию 'all')
  stats?: PriceStats        // если передан — рисуем overlays
}

const WINDOW_DAYS: Record<PriceWindow, number | null> = {
  '7d': 7,
  '30d': 30,
  'all': null,
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-scout border border-scout-border bg-scout-elevated p-3 text-sm shadow-xl">
      <p className="mb-1 text-scout-muted">{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} className="font-semibold" style={{ color: p.color }}>
          {formatPrice(p.value)}
        </p>
      ))}
    </div>
  )
}

export function PriceChart({ productId, targetPrice, window = 'all', stats }: PriceChartProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['price-history', productId],
    queryFn: () => productsApi.priceHistory(productId),
  })

  // Фильтрация по окну
  const filtered = useMemo(() => {
    if (!data?.length) return []
    const days = WINDOW_DAYS[window]
    if (days === null) return data
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - days + 1)
    cutoff.setHours(0, 0, 0, 0)
    return data.filter(d => new Date(d.timestamp) >= cutoff)
  }, [data, window])

  // Подготовка данных для chart
  const { chartData, sources, minP, maxP, dateLabelByISO } = useMemo(() => {
    const grouped = filtered.reduce<Record<string, PriceHistory[]>>((acc, item) => {
      acc[item.source] = acc[item.source] ?? []
      acc[item.source].push(item)
      return acc
    }, {})
    const sources = Object.keys(grouped)
    const allDates = [...new Set(filtered.map(d => d.timestamp.slice(0, 10)))].sort()
    const dateLabelByISO: Record<string, string> = {}
    for (const d of allDates) dateLabelByISO[d] = formatDate(d)

    const chartData = allDates.map(date => {
      const entry: Record<string, string | number> = { date: dateLabelByISO[date] }
      for (const src of sources) {
        const match = grouped[src].find(d => d.timestamp.startsWith(date))
        if (match) entry[src] = match.price
      }
      return entry
    })

    const allPrices = filtered.map(d => d.price)
    const minP = allPrices.length ? Math.min(...allPrices) : 0
    const maxP = allPrices.length ? Math.max(...allPrices) : 0
    return { chartData, sources, minP, maxP, dateLabelByISO }
  }, [filtered])

  // Подбираем нужное окно агрегатов из stats
  const statsWindow = useMemo(() => {
    if (!stats) return null
    if (window === '7d') return stats.window_7d
    if (window === '30d') return stats.window_30d
    return stats.all_time
  }, [stats, window])

  if (isLoading) return <PageSpinner />
  if (!data?.length) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-scout-dim">
        История цен недоступна
      </div>
    )
  }
  if (!chartData.length) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-scout-dim">
        Нет данных за выбранный период
      </div>
    )
  }

  const pad = (maxP - minP) * 0.15 || maxP * 0.05 || 1
  const avg = statsWindow && 'avg' in statsWindow ? (statsWindow.avg ?? null) : null

  // ReferenceDot.x должен совпадать со значением dataKey="date" (то есть formatDate(...))
  const minDotX = statsWindow?.min_date ? dateLabelByISO[statsWindow.min_date] : null
  const maxDotX = statsWindow?.max_date ? dateLabelByISO[statsWindow.max_date] : null
  // Найдём ли мы такую X-метку в текущем chartData? (если min/max снаружи окна — нет)
  const hasMinDot = !!(minDotX && chartData.some(d => d.date === minDotX))
  const hasMaxDot = !!(maxDotX && chartData.some(d => d.date === maxDotX))

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={chartData} margin={{ top: 12, right: 16, left: 0, bottom: 0 }}>
        <defs>
          {sources.map(src => (
            <linearGradient key={src} id={`grad-${src}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={SOURCE_COLORS[src] ?? '#6346f5'} stopOpacity={0.25} />
              <stop offset="95%" stopColor={SOURCE_COLORS[src] ?? '#6346f5'} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis
          dataKey="date"
          tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[Math.max(0, minP - pad), maxP + pad]}
          tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={v => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)}
          width={44}
        />
        <Tooltip content={<CustomTooltip />} />

        {/* Линия средней цены за выбранное окно */}
        {avg !== null && (
          <ReferenceLine
            y={avg}
            stroke="#a78bfa"
            strokeDasharray="4 4"
            strokeWidth={1.5}
          >
            <Label value={`Ср. ${formatPrice(avg)}`} fill="#a78bfa" fontSize={11} position="insideTopRight" />
          </ReferenceLine>
        )}

        {/* Целевая цена подписки */}
        {targetPrice && (
          <ReferenceLine
            y={targetPrice}
            stroke="#10B981"
            strokeDasharray="6 3"
          >
            <Label value={`Цель ${formatPrice(targetPrice)}`} fill="#10B981" fontSize={11} position="insideBottomRight" />
          </ReferenceLine>
        )}

        {/* Маркер минимума */}
        {hasMinDot && statsWindow?.min != null && (
          <ReferenceDot
            x={minDotX as string}
            y={statsWindow.min}
            r={6}
            fill="#10B981"
            stroke="#0A0A0A"
            strokeWidth={2}
            ifOverflow="extendDomain"
          >
            <Label value={`min ${formatPrice(statsWindow.min)}`} fill="#10B981" fontSize={11} position="top" />
          </ReferenceDot>
        )}

        {/* Маркер максимума */}
        {hasMaxDot && statsWindow?.max != null && (
          <ReferenceDot
            x={maxDotX as string}
            y={statsWindow.max}
            r={6}
            fill="#ef4444"
            stroke="#0A0A0A"
            strokeWidth={2}
            ifOverflow="extendDomain"
          >
            <Label value={`max ${formatPrice(statsWindow.max)}`} fill="#ef4444" fontSize={11} position="top" />
          </ReferenceDot>
        )}

        {sources.map(src => (
          <Area
            key={src}
            type="monotone"
            dataKey={src}
            stroke={SOURCE_COLORS[src] ?? '#6346f5'}
            strokeWidth={2}
            fill={`url(#grad-${src})`}
            connectNulls
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  )
}
