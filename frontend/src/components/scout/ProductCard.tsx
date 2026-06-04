import { TrendingDown } from 'lucide-react'
import { MarketplaceTag, type MarketplaceSource } from './MarketplaceTag'
import { ImagePlaceholder } from './ImagePlaceholder'
import { fmt } from './utils'

export interface ScoutProductCardData {
  id: number | string
  name: string
  category: string
  source: MarketplaceSource
  price: number
  oldPrice: number | null
  discountPct: number | null
  isPriceMin?: boolean
  stock?: boolean
  lastSeen?: string
  imageUrl?: string | null
}

interface ScoutProductCardProps {
  product: ScoutProductCardData
  onClick?: () => void
}

export function ScoutProductCard({ product, onClick }: ScoutProductCardProps) {
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

      <div className="mt-4 relative">
        <ImagePlaceholder
          width="100%"
          height={140}
          label="product shot"
          src={product.imageUrl}
        />
        {product.discountPct != null && product.discountPct > 0 && (
          <span className="absolute top-2 left-2 rounded-scout bg-scout-success px-2 py-1 text-[12px] font-bold text-scout-bg scout-tabnums">
            −{product.discountPct}%
          </span>
        )}
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
        {product.oldPrice != null && product.oldPrice > product.price && (
          <span className="text-[13px] text-scout-dim line-through scout-tabnums">
            {fmt(product.oldPrice)} ₽
          </span>
        )}
      </div>

      <div className="mt-3.5 flex items-center justify-between gap-2">
        {product.isPriceMin ? (
          <span className="inline-flex items-center gap-1.5 rounded-scout border border-scout-accent/30 bg-scout-accent/10 px-2 py-1 text-[11px] font-medium uppercase tracking-[0.06em] text-scout-accent">
            <TrendingDown size={12} />
            исторический минимум
          </span>
        ) : (
          <span />
        )}
        {product.lastSeen && (
          <span className="text-[11px] text-scout-dim shrink-0">{product.lastSeen}</span>
        )}
      </div>
    </button>
  )
}
