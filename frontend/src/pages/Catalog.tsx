import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { ProductCard } from '@/components/ProductCard'
import { AddSubscriptionModal } from '@/components/AddSubscriptionModal'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { PageSpinner } from '@/components/ui/Spinner'
import { productsApi, categoriesApi } from '@/api/products'
import { subscriptionsApi } from '@/api/subscriptions'
import { wishlistApi } from '@/api/wishlist'
import { useDebounce } from '@/hooks/useDebounce'
import type { Product } from '@/types'

const ORDERINGS = [
  { value: '',      label: 'По умолчанию' },
  { value: 'name',  label: 'Название А–Я' },
  { value: '-name', label: 'Название Я–А' },
]

const SOURCES = ['', 'dns', 'citilink', 'ozon']
const SOURCE_LABELS: Record<string, string> = { '': 'Все магазины', dns: 'DNS', citilink: 'Ситилинк', ozon: 'Ozon' }

const SELECT_CLS = 'rounded-steam border border-steam-border bg-steam-darker px-3 py-2 text-sm text-steam-light focus:border-steam-blue focus:outline-none'

export default function Catalog() {
  const [search, setSearch] = useState('')
  const [ordering, setOrdering] = useState('')
  const [source, setSource] = useState('')
  const [categorySlug, setCategorySlug] = useState('')
  const [page, setPage] = useState(1)
  const [subscribeTarget, setSubscribeTarget] = useState<Product | null>(null)

  const debouncedSearch = useDebounce(search, 400)

  const { data: categoriesData } = useQuery({
    queryKey: ['categories'],
    queryFn: categoriesApi.list,
    staleTime: 300_000,
  })
  const categories = categoriesData?.results ?? []

  const { data, isLoading } = useQuery({
    queryKey: ['products', debouncedSearch, ordering, source, categorySlug, page],
    queryFn: () => productsApi.list({
      search: debouncedSearch,
      ordering,
      source,
      ...(categorySlug ? { category_slug: categorySlug } : {}),
      page,
      page_size: 24,
    }),
  })

  const { data: subs } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: subscriptionsApi.list,
  })
  const subscribedIds = new Set(subs?.results.map(s => s.product.id) ?? [])

  const { data: wishlist } = useQuery({
    queryKey: ['wishlist'],
    queryFn: wishlistApi.get,
  })
  const wishlistMap = new Map(wishlist?.items.map(i => [i.product.id, i.id]) ?? [])

  return (
    <>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white mb-1">Каталог товаров</h1>
        <div className="h-px bg-steam-border mb-4" />

        <div className="bg-steam-card border border-steam-border rounded-steam p-3 flex flex-wrap items-center gap-2">
          <div className="flex-1 min-w-[220px]">
            <Input
              icon={<Search size={14} />}
              placeholder="Поиск по названию, бренду..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
            />
          </div>

          <select
            value={categorySlug}
            onChange={e => { setCategorySlug(e.target.value); setPage(1) }}
            className={SELECT_CLS}
          >
            <option value="">Все категории</option>
            {categories.map(c => (
              <option key={c.slug} value={c.slug}>{c.name}</option>
            ))}
          </select>

          <select
            value={source}
            onChange={e => { setSource(e.target.value); setPage(1) }}
            className={SELECT_CLS}
          >
            {SOURCES.map(s => (
              <option key={s} value={s}>{SOURCE_LABELS[s]}</option>
            ))}
          </select>

          <select
            value={ordering}
            onChange={e => setOrdering(e.target.value)}
            className={SELECT_CLS}
          >
            {ORDERINGS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {data && (
          <p className="mt-2 text-xs text-steam-muted">
            Найдено: <span className="text-steam-light">{data.count}</span> товаров
          </p>
        )}
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {data?.results.map((product, i) => (
              <ProductCard
                key={product.id}
                product={product}
                index={i}
                onSubscribe={setSubscribeTarget}
                subscribed={subscribedIds.has(product.id)}
                wishlistItemId={wishlistMap.get(product.id) ?? null}
              />
            ))}
          </div>

          {data?.results.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-20 text-steam-muted">
              <Search size={40} strokeWidth={1.5} />
              <p className="text-base text-steam-light">Ничего не найдено</p>
              <p className="text-xs">Попробуйте изменить поиск или фильтры</p>
            </div>
          )}

          {data && data.count > 24 && (
            <div className="mt-6 flex items-center justify-center gap-3">
              <Button
                variant="secondary"
                disabled={!data.previous}
                onClick={() => setPage(p => p - 1)}
              >
                Назад
              </Button>
              <span className="text-xs text-steam-muted">
                Стр. {page} из {Math.ceil(data.count / 24)}
              </span>
              <Button
                variant="secondary"
                disabled={!data.next}
                onClick={() => setPage(p => p + 1)}
              >
                Вперёд
              </Button>
            </div>
          )}
        </>
      )}

      <AddSubscriptionModal
        open={!!subscribeTarget}
        onClose={() => setSubscribeTarget(null)}
        preselectedProduct={subscribeTarget ?? undefined}
      />
    </>
  )
}
