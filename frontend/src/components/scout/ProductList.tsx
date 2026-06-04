import { TrendingDown } from 'lucide-react'
import { MarketplaceTag } from './MarketplaceTag'
import { ImagePlaceholder } from './ImagePlaceholder'
import { fmt } from './utils'
import type { ScoutProductCardData } from './ProductCard'

interface ProductListProps {
  products: ScoutProductCardData[]
  onOpen?: (p: ScoutProductCardData) => void
}

const COLS = '40px 1fr 120px 120px 110px 150px 60px'

export function ProductList({ products, onOpen }: ProductListProps) {
  return (
    <div className="bg-scout-elevated border border-scout-subtle rounded-scout-lg overflow-x-auto">
      <div className="min-w-[760px]">
      <div
        className="grid gap-4 px-4 py-3 border-b border-scout-subtle text-[10px] text-scout-dim uppercase tracking-[0.1em]"
        style={{ gridTemplateColumns: COLS }}
      >
        <span />
        <span>товар</span>
        <span>маркетплейс</span>
        <span className="text-right">цена</span>
        <span className="text-right">было</span>
        <span>статус</span>
        <span />
      </div>

      {products.map((p, i) => (
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
          <span className="text-xs text-right scout-tabnums text-scout-dim line-through">
            {p.oldPrice != null && p.oldPrice > p.price ? `${fmt(p.oldPrice)} ₽` : ''}
          </span>
          <span className="flex items-center gap-1.5">
            {p.discountPct != null && p.discountPct > 0 && (
              <span className="rounded-scout bg-scout-success/15 px-1.5 py-0.5 text-[11px] font-bold text-scout-success scout-tabnums">
                −{p.discountPct}%
              </span>
            )}
            {p.isPriceMin && (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-scout-accent">
                <TrendingDown size={11} /> мин
              </span>
            )}
          </span>
          <span className="text-scout-dim text-right">···</span>
        </button>
      ))}
      </div>
    </div>
  )
}
