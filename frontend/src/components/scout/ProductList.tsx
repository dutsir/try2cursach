import { MarketplaceTag } from './MarketplaceTag'
import { ImagePlaceholder } from './ImagePlaceholder'
import { Sparkline } from './Sparkline'
import { VerdictBadge } from './VerdictBadge'
import { computeTrend, fmt } from './utils'
import type { ScoutProductCardData } from './ProductCard'

interface ProductListProps {
  products: ScoutProductCardData[]
  onOpen?: (p: ScoutProductCardData) => void
}

const COLS = '40px 1fr 120px 130px 100px 130px 96px 60px'

export function ProductList({ products, onOpen }: ProductListProps) {
  return (
    <div className="bg-scout-elevated border border-scout-subtle rounded-scout-lg overflow-hidden">
      <div
        className="grid gap-4 px-4 py-3 border-b border-scout-subtle text-[10px] text-scout-dim uppercase tracking-[0.1em]"
        style={{ gridTemplateColumns: COLS }}
      >
        <span />
        <span>товар</span>
        <span>маркетплейс</span>
        <span className="text-right">цена</span>
        <span className="text-right">тренд</span>
        <span>график</span>
        <span>вердикт</span>
        <span />
      </div>

      {products.map((p, i) => {
        const t = computeTrend(p.price, p.prev)
        return (
          <button
            key={p.id}
            onClick={() => onOpen?.(p)}
            className={`grid gap-4 px-4 py-3.5 items-center text-left w-full cursor-pointer hover:bg-scout-subtle/40 transition-colors ${
              i === 0 ? '' : 'border-t border-scout-subtle'
            }`}
            style={{ gridTemplateColumns: COLS }}
          >
            <ImagePlaceholder width={28} height={28} label="" src={p.imageUrl} />
            <span className="text-[13px] font-medium text-scout-text truncate">
              {p.name}
            </span>
            <MarketplaceTag source={p.source} />
            <span className="text-sm font-semibold text-right scout-tabnums text-scout-text">
              {fmt(p.price)} ₽
            </span>
            <span
              className="text-xs font-semibold text-right"
              style={{ color: t.color }}
            >
              {t.arrow} {t.abs.toFixed(1)}%
            </span>
            <Sparkline data={p.series} width={120} height={28} color={t.color} />
            <VerdictBadge verdict={p.verdict} />
            <span className="text-scout-dim text-right">···</span>
          </button>
        )
      })}
    </div>
  )
}
