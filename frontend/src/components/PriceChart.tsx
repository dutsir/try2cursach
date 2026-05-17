import { useQuery } from '@tanstack/react-query'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { productsApi } from '@/api/products'
import { formatPrice, formatDate, SOURCE_COLORS } from '@/lib/utils'
import { PageSpinner } from '@/components/ui/Spinner'
import type { PriceHistory } from '@/types'

interface PriceChartProps {
  productId: number
  targetPrice?: number
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-white/15 bg-slate-900/95 p-3 text-sm shadow-xl backdrop-blur-xl">
      <p className="mb-1 text-white/50">{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} className="font-semibold" style={{ color: p.color }}>
          {formatPrice(p.value)}
        </p>
      ))}
    </div>
  )
}

export function PriceChart({ productId, targetPrice }: PriceChartProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['price-history', productId],
    queryFn: () => productsApi.priceHistory(productId),
  })

  if (isLoading) return <PageSpinner />
  if (!data?.length) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-white/40">
        История цен недоступна
      </div>
    )
  }

  const grouped = data.reduce<Record<string, PriceHistory[]>>((acc, item) => {
    acc[item.source] = acc[item.source] ?? []
    acc[item.source].push(item)
    return acc
  }, {})

  const sources = Object.keys(grouped)

  const allDates = [...new Set(data.map(d => d.timestamp.slice(0, 10)))].sort()
  const chartData = allDates.map(date => {
    const entry: Record<string, string | number> = { date: formatDate(date) }
    for (const src of sources) {
      const match = grouped[src].find(d => d.timestamp.startsWith(date))
      if (match) entry[src] = match.price
    }
    return entry
  })

  const allPrices = data.map(d => d.price)
  const minP = Math.min(...allPrices)
  const maxP = Math.max(...allPrices)
  const pad = (maxP - minP) * 0.1

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
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
          domain={[minP - pad, maxP + pad]}
          tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={v => `${(v / 1000).toFixed(0)}k`}
          width={40}
        />
        <Tooltip content={<CustomTooltip />} />
        {targetPrice && (
          <ReferenceLine
            y={targetPrice}
            stroke="#22c55e"
            strokeDasharray="6 3"
            label={{ value: 'Цель', fill: '#22c55e', fontSize: 11, position: 'right' }}
          />
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
