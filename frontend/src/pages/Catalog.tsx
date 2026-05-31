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
  { value: '',            label: 'По умолчанию' },
  { value: 'min_price',   label: 'Дешевле сначала' },
  { value: '-min_price',  label: 'Дороже сначала' },
  { value: 'name',        label: 'Название А–Я' },
  { value: '-name',       label: 'Название Я–А' },
  { value: '-created_at', label: 'Новинки' },
]

const PAGE_SIZE = 24

export default function Catalog() {
  const f = useCatalogFilters()
  const [searchLocal, setSearchLocal] = useState(f.search)
  const [subscribeTarget, setSubscribeTarget] = useState<Product | null>(null)
  const debouncedSearch = useDebounce(searchLocal, 400)

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

  const { data: categoryTree } = useQuery({
    queryKey: ['categories-tree'],
    queryFn: categoriesApi.tree,
    staleTime: 300_000,
  })
  const roots = categoryTree ?? []

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

  const { ref: sentinelRef, inView } = useInView({ rootMargin: '600px' })
  useEffect(() => {
    if (inView && hasNextPage && !isFetchingNextPage) fetchNextPage()
  }, [inView, hasNextPage, isFetchingNextPage, fetchNextPage])

  return (
    <div className="animate-scout-rise grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-0 -mx-6 lg:-mx-10 -my-8">
      <CatalogSidebar />

      <main className="px-6 lg:px-8 py-8 min-w-0 pb-32">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="scout-caption">catalog</div>
            <h1 className="mt-2 font-display text-[40px] font-bold tracking-[-0.02em] lowercase text-scout-text">
              каталог
            </h1>
            {total > 0 && (
              <p className="mt-1 text-sm text-scout-muted">
                найдено <span className="text-scout-text scout-tabnums">{total.toLocaleString('ru-RU')}</span> товаров
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <select
              value={f.category}
              onChange={e => f.setFilter('category', e.target.value)}
              className="rounded-scout border border-scout-subtle bg-scout-elevated px-3 py-2 text-sm text-scout-text focus:border-scout-accent/60 focus:outline-none max-w-[220px]"
            >
              <option value="">Все категории</option>
              {roots.map(root => (
                root.children.length > 0 ? (
                  <optgroup key={root.slug} label={`${root.name} (${root.product_count})`}>
                    <option value={root.slug}>Все · {root.name}</option>
                    {root.children.map(child => (
                      <option key={child.slug} value={child.slug}>
                        {child.name} ({child.product_count})
                      </option>
                    ))}
                  </optgroup>
                ) : (
                  <option key={root.slug} value={root.slug}>
                    {root.name} ({root.product_count})
                  </option>
                )
              ))}
            </select>

            <select
              value={f.ordering}
              onChange={e => f.setFilter('ordering', e.target.value)}
              className="rounded-scout border border-scout-subtle bg-scout-elevated px-3 py-2 text-sm text-scout-text focus:border-scout-accent/60 focus:outline-none"
            >
              {ORDERINGS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="mb-6">
          <Input
            icon={<Search size={14} />}
            placeholder="Поиск по названию, бренду, артикулу…"
            value={searchLocal}
            onChange={e => setSearchLocal(e.target.value)}
          />
        </div>

        {isLoading ? (
          <div className="flex justify-center py-20"><Spinner /></div>
        ) : products.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-24 text-center">
            <Search size={40} strokeWidth={1.5} className="text-scout-dim" />
            <p className="text-base text-scout-text">Ничего не найдено</p>
            <p className="text-xs text-scout-muted">Попробуй изменить фильтры или сбросить</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
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

            <div ref={sentinelRef} className="h-16 flex items-center justify-center">
              {isFetchingNextPage && (
                <span className="flex items-center gap-2 text-xs text-scout-dim">
                  <Loader2 size={14} className="animate-spin" />
                  Загрузка ещё…
                </span>
              )}
              {!hasNextPage && products.length > 0 && (
                <span className="text-xs text-scout-dim">это всё.</span>
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
