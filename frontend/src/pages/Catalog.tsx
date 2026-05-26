import { useEffect, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { useInView } from 'react-intersection-observer'
import { Search, Loader2 } from 'lucide-react'
import { ProductCard } from '@/components/ProductCard'
import { CatalogSidebar } from '@/components/CatalogSidebar'
import { CompareBar } from '@/components/CompareBar'
import { AddSubscriptionModal } from '@/components/AddSubscriptionModal'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { productsApi, categoriesApi } from '@/api/products'
import { subscriptionsApi } from '@/api/subscriptions'
import { wishlistApi } from '@/api/wishlist'
import { useDebounce } from '@/hooks/useDebounce'
import { useCatalogFilters } from '@/hooks/useCatalogFilters'
import type { Product, PaginatedResponse } from '@/types'

const ORDERINGS = [
  { value: '',           label: 'По умолчанию' },
  { value: 'min_price',  label: 'Дешевле сначала' },
  { value: '-min_price', label: 'Дороже сначала' },
  { value: 'name',       label: 'Название А–Я' },
  { value: '-name',      label: 'Название Я–А' },
  { value: '-created_at', label: 'Новинки' },
]

const PAGE_SIZE = 24

export default function Catalog() {
  const f = useCatalogFilters()
  const [searchLocal, setSearchLocal] = useState(f.search)
  const [subscribeTarget, setSubscribeTarget] = useState<Product | null>(null)
  const debouncedSearch = useDebounce(searchLocal, 400)

  // Синхронизация локального search с URL
  useEffect(() => {
    if (debouncedSearch !== f.search) {
      f.setFilter('search', debouncedSearch)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch])

  useEffect(() => {
    if (f.search !== searchLocal) setSearchLocal(f.search)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f.search])

  const { data: categoriesData } = useQuery({
    queryKey: ['categories'],
    queryFn: categoriesApi.list,
    staleTime: 300_000,
  })
  const categories = categoriesData?.results ?? []

  const apiParams = f.toApiParams()
  const queryKey = ['products-inf', apiParams]

  const {
    data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading,
  } = useInfiniteQuery<PaginatedResponse<Product>>({
    queryKey,
    queryFn: ({ pageParam }) =>
      productsApi.list({ ...apiParams, page: pageParam as number, page_size: PAGE_SIZE }),
    initialPageParam: 1,
    getNextPageParam: (lastPage, allPages) => lastPage.next ? allPages.length + 1 : undefined,
  })

  const products = data?.pages.flatMap(p => p.results) ?? []
  const total = data?.pages[0]?.count ?? 0

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

  // Auto-fetch при появлении sentinel в viewport
  const { ref: sentinelRef, inView } = useInView({ rootMargin: '600px' })
  useEffect(() => {
    if (inView && hasNextPage && !isFetchingNextPage) fetchNextPage()
  }, [inView, hasNextPage, isFetchingNextPage, fetchNextPage])

  return (
    <div className="grid grid-cols-1 gap-0 lg:grid-cols-[260px_1fr] -mx-4">
      <CatalogSidebar />

      <main className="px-4 lg:px-6 py-4 min-w-0">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
          <h1 className="text-xl font-bold text-white">Каталог</h1>
          {total > 0 && (
            <span className="text-xs text-steam-muted">
              Найдено: <span className="text-steam-light">{total.toLocaleString('ru-RU')}</span>
            </span>
          )}

          <div className="ml-auto flex gap-2">
            <select
              value={f.category}
              onChange={e => f.setFilter('category', e.target.value)}
              className="rounded-steam border border-steam-border bg-steam-darker px-3 py-2 text-sm text-steam-light focus:border-steam-blue focus:outline-none max-w-[220px]"
            >
              <option value="">Все категории</option>
              {categories.map(c => (
                <option key={c.slug} value={c.slug}>{c.name}</option>
              ))}
            </select>

            <select
              value={f.ordering}
              onChange={e => f.setFilter('ordering', e.target.value)}
              className="rounded-steam border border-steam-border bg-steam-darker px-3 py-2 text-sm text-steam-light focus:border-steam-blue focus:outline-none"
            >
              {ORDERINGS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="mb-4">
          <Input
            icon={<Search size={14} />}
            placeholder="Поиск по названию, бренду, артикулу..."
            value={searchLocal}
            onChange={e => setSearchLocal(e.target.value)}
          />
        </div>

        {isLoading ? (
          <div className="flex justify-center py-20"><Spinner /></div>
        ) : products.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-20 text-steam-muted">
            <Search size={40} strokeWidth={1.5} />
            <p className="text-base text-steam-light">Ничего не найдено</p>
            <p className="text-xs">Попробуйте изменить фильтры или сбросить</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {products.map((product, i) => (
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

            <div ref={sentinelRef} className="h-12 flex items-center justify-center">
              {isFetchingNextPage && (
                <span className="flex items-center gap-2 text-xs text-steam-muted">
                  <Loader2 size={14} className="animate-spin" />
                  Загрузка ещё…
                </span>
              )}
              {!hasNextPage && products.length > 0 && (
                <span className="text-xs text-steam-muted">Это всё.</span>
              )}
            </div>
          </>
        )}
      </main>

      <CompareBar />

      <AddSubscriptionModal
        open={!!subscribeTarget}
        onClose={() => setSubscribeTarget(null)}
        preselectedProduct={subscribeTarget ?? undefined}
      />
    </div>
  )
}
