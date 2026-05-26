import { Link } from 'react-router-dom'
import { Package } from 'lucide-react'
import { formatPrice, SOURCE_LABELS } from '@/lib/utils'
import type { DashboardDeal } from '@/api/dashboard'

interface Props {
  deal: DashboardDeal
}

export function DealCard({ deal }: Props) {
  return (
    <Link
      to={`/products/${deal.id}`}
      className="group flex flex-col gap-2 min-w-[200px] max-w-[200px] rounded-steam border border-steam-border bg-steam-card overflow-hidden transition-colors hover:border-steam-blue/60"
    >
      <div className="relative flex h-32 items-center justify-center bg-steam-darker">
        {deal.image_url ? (
          <img src={deal.image_url} alt={deal.name} className="h-full w-full object-contain p-2" />
        ) : (
          <Package size={28} className="text-steam-border" />
        )}
        <span className="absolute top-1 right-1 rounded-steam bg-steam-green px-1.5 py-0.5 text-[10px] font-bold text-steam-darker">
          −{deal.discount_pct}%
        </span>
      </div>
      <div className="px-2 pb-2 flex flex-col gap-1">
        {deal.brand && (
          <span className="text-[9px] uppercase tracking-wider text-steam-muted">{deal.brand}</span>
        )}
        <span className="text-xs font-medium text-steam-light line-clamp-2 min-h-[32px]">{deal.name}</span>
        <div className="mt-auto flex items-baseline gap-2">
          <span className="text-sm font-bold text-steam-green">{formatPrice(Number(deal.price))}</span>
          <span className="text-[10px] text-steam-muted line-through">{formatPrice(Number(deal.old_price))}</span>
        </div>
        <span className="text-[9px] uppercase tracking-wider text-steam-muted">{SOURCE_LABELS[deal.source] ?? deal.source}</span>
      </div>
    </Link>
  )
}
