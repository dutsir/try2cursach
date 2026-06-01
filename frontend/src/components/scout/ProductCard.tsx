import { MarketplaceTag, type MarketplaceSource } from './MarketplaceTag'
import { ImagePlaceholder } from './ImagePlaceholder'
import { Sparkline } from './Sparkline'
import { VerdictBadge, type Verdict } from './VerdictBadge'
import { computeTrend, fmt } from './utils'

export interface ScoutProductCardData {
  id: number | string
  name: string
  category: string
  source: MarketplaceSource
  price: number
  prev: number
  verdict: Verdict
  series: number[]
  stock?: boolean
  lastSeen?: string
  imageUrl?: string | null
}

interface ScoutProductCardProps {
  product: ScoutProductCardData
  onClick?: () => void
}

export function ScoutProductCard({ product, onClick }: ScoutProductCardProps) {
  const t = computeTrend(product.price, product.prev)

  return (
    <button
      onClick={onClick}
      className="text-left bg-scout-elevated border border-scout-subtle hover:border-scout-border rounded-scout-lg p-5 cursor-pointer transition-all duration-200 hover:-translate-y-0.5 relative w-full"
    >
      <div className="flex items-center gap-2">
        <MarketplaceTag source={product.source} />
        {product.stock === false && (
          <span className="text-[11px] text-scout-dim">· нет в наличии</span>
        )}
      </div>

      <div className="mt-4">
        <ImagePlaceholder
          width="100%"
          height={140}
          label="product shot"
          src={product.imageUrl}
        />
      </div>

      <div className="mt-3 text-[10px] text-scout-dim uppercase tracking-[0.08em]">
        {product.category}
      </div>
      <div className="mt-1.5 text-[15px] font-semibold leading-[1.3] text-scout-text h-10 overflow-hidden">
        {product.name}
      </div>

      <div className="mt-3.5 flex items-baseline gap-2.5 flex-wrap">
        <span className="font-sans text-[26px] font-bold text-scout-text tracking-[-0.01em] scout-tabnums">
          {fmt(product.price)} ₽
        </span>
        <span className="text-[13px] text-scout-dim line-through scout-tabnums">
          {fmt(product.prev)} ₽
        </span>
      </div>

      <div
        className="mt-1 text-xs font-semibold"
        style={{ color: t.color }}
      >
        {t.arrow} {t.abs.toFixed(1)}% · {fmt(t.diff)} ₽
      </div>

      <div className="mt-3">
        <Sparkline data={product.series} width={320} height={48} color={t.color} />
      </div>

      <div className="mt-3.5 flex items-center justify-between">
        <VerdictBadge verdict={product.verdict} />
        {product.lastSeen && (
          <span className="text-[11px] text-scout-dim">{product.lastSeen}</span>
        )}
      </div>
    </button>
  )
}
