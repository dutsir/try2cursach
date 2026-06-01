import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { productsApi } from '@/api/products'
import { dashboardApi } from '@/api/dashboard'
import { Spinner } from '@/components/ui/Spinner'
import { useAuth } from '@/hooks/useAuth'
import {
  DashHeader,
  DashStats,
  ScoutProductCard,
  ProductList,
  EmptyDash,
  genSeries,
  type DashFilter,
  type DashView,
  type ScoutProductCardData,
  type Verdict,
  type MarketplaceSource,
} from '@/components/scout'
import { cn } from '@/lib/utils'
import type { Product } from '@/types'

function toScoutCard(p: Product): ScoutProductCardData {
  const offer = p.best_offer
  const priceStr = offer?.current_price ?? (offer?.price?.toString() ?? '0')
  const oldStr = offer?.old_price ?? null
  const price = parseFloat(priceStr) || 0
  const prev = oldStr ? parseFloat(oldStr) || price : Math.round(price * 1.08)

  const verdict = inferVerdict(price, prev)

  return {
    id: p.id,
    name: p.name,
    category: `${p.category?.name ?? '—'}${p.brand ? ` · ${p.brand}` : ''}`,
    source: (offer?.source ?? 'wb') as MarketplaceSource,
    price,
    prev,
    verdict,
    series: genSeries(20, prev, price),
    stock: offer?.is_available ?? true,
    lastSeen: offer?.last_seen_at ? formatRelative(offer.last_seen_at) : undefined,
    imageUrl: offer?.image_url ?? null,
  }
}

function inferVerdict(price: number, prev: number): Verdict {
  if (!prev || prev === price) return 'monitor'
  const delta = (price - prev) / prev
  if (delta <= -0.05) return 'buy'
  if (delta >= 0.02) return 'wait'
  return 'monitor'
}

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.round(diff / 60_000)
  if (m < 1) return 'только что'
  if (m < 60) return `${m} мин назад`
  const h = Math.round(m / 60)
  if (h < 24) return `${h} ч назад`
  const d = Math.round(h / 24)
  return `${d} дн назад`
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { user } = useAuth()

  const [view, setView] = useState<DashView>('grid')
  const [filter, setFilter] = useState<DashFilter>('all')
  const [catSlug, setCatSlug] = useState<string | null>(null)

  const { data: products, isLoading } = useQuery({
    queryKey: ['products', { page_size: 24, ordering: '-last_parsed_at', category_slug: catSlug }],
    queryFn: () =>
      productsApi.list({
        page_size: 24,
        ordering: '-last_parsed_at',
        ...(catSlug ? { category_slug: catSlug } : {}),
      }),
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  })

  const { data: dash } = useQuery({
    queryKey: ['dashboard'],
    queryFn: dashboardApi.get,
    staleTime: 5 * 60_000,
  })

  const categories = dash?.popular_categories ?? []

  const cards: ScoutProductCardData[] = useMemo(
    () => (products?.results ?? []).map(toScoutCard),
    [products],
  )

  const counts = useMemo(() => {
    const c: Record<DashFilter, number> = { all: cards.length, buy: 0, wait: 0, monitor: 0 }
    for (const card of cards) c[card.verdict]++
    return c
  }, [cards])

  const filtered = filter === 'all' ? cards : cards.filter(c => c.verdict === filter)
  const totalTracked = dash?.totals?.products ?? cards.length
  const totalOffers = dash?.totals?.offers ?? 0
  const greetingName = (user?.first_name || user?.username || '').toLowerCase()

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    )
  }

  if (cards.length === 0 && catSlug === null) {
    return <EmptyDash />
  }

  return (
    <div className="animate-scout-rise">
      <DashHeader
        filter={filter}
        setFilter={setFilter}
        view={view}
        setView={setView}
        greeting={greetingName ? `добрый день, ${greetingName}.` : 'добрый день.'}
        subtitle={`${counts.buy} товаров готовы к покупке. ${counts.wait} стоит подождать.`}
        counts={counts}
      />

      <DashStats tracked={totalTracked} offersCount={totalOffers} />

      {categories.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          <button
            onClick={() => setCatSlug(null)}
            className={cn(
              'rounded-scout px-3 py-1.5 text-[13px] font-medium transition-colors border',
              catSlug === null
                ? 'bg-scout-accent text-scout-text border-scout-accent'
                : 'bg-scout-elevated text-scout-muted border-scout-subtle hover:text-scout-text hover:border-scout-border',
            )}
          >
            Все
          </button>
          {categories.map(c => (
            <button
              key={c.slug}
              onClick={() => setCatSlug(c.slug)}
              className={cn(
                'rounded-scout px-3 py-1.5 text-[13px] font-medium transition-colors border inline-flex items-center gap-1.5',
                catSlug === c.slug
                  ? 'bg-scout-accent text-scout-text border-scout-accent'
                  : 'bg-scout-elevated text-scout-muted border-scout-subtle hover:text-scout-text hover:border-scout-border',
              )}
            >
              {c.name}
              <span className="text-[11px] text-scout-dim scout-tabnums">{c.count}</span>
            </button>
          ))}
        </div>
      )}

      {view === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(p => (
            <ScoutProductCard
              key={p.id}
              product={p}
              onClick={() => navigate(`/products/${p.id}`)}
            />
          ))}
        </div>
      ) : (
        <ProductList
          products={filtered}
          onOpen={p => navigate(`/products/${p.id}`)}
        />
      )}

      {filtered.length === 0 && (
        <div className="py-20 text-center text-scout-muted">
          нет товаров под этот фильтр.
        </div>
      )}
    </div>
  )
}
