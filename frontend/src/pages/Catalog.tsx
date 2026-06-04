import { useEffect, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { useInView } from 'react-intersection-observer'
import { Search, Loader2 } from 'lucide-react'
import { ProductCard } from '@/components/ProductCard'
import { CatalogSidebar } from '@/components/CatalogSidebar'
import { ActiveFilters } from '@/components/ActiveFilters'
import { CompareBar } from '@/components/CompareBar'
import { AddSubscriptionModal } from '@/components/AddSubscriptionModal'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { parseApiError } from '@/api/client'
import { productsApi, categoriesApi } from '@/api/products'
import { QueryError } from '@/components/ui/QueryError'
import { subscriptionsApi } from '@/api/subscriptions'
import { wishlistApi } from '@/api/wishlist'
import { useDebounce } from '@/hooks/useDebounce'
import { useCatalogFilters } from '@/hooks/useCatalogFilters'
import type { Product, PaginatedResponse } from '@/types'

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

  const {
    data: categoryTree,
    isError: treeError,
    error: treeErr,
    refetch: refetchTree,
  } = useQuery({
    queryKey: ['categories-tree'],
    queryFn: categoriesApi.tree,
    staleTime: 300_000,
  })
  const roots = categoryTree ?? []

  // Категория обязательна: при заходе без выбранной — встаём на первую корневую.
  useEffect(() => {
    if (!f.category && roots.length) {
      f.setCategory(roots[0].slug, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f.category, roots])

  const apiParams = f.toApiParams()
  const queryKey = ['products-inf', apiParams]

  const {
    data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading,
    isError: productsError, error: productsErr, refetch: refetchProducts,
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
    <div className="animate-scout-rise grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-0 -mx-4 sm:-mx-6 lg:-mx-10 -my-6 sm:-my-8">
      <CatalogSidebar />

      <main className="px-4 sm:px-6 lg:px-8 py-6 sm:py-8 min-w-0 pb-32">
        <div className="mb-6">
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

        <div className="mb-6">
          <Input
            icon={<Search size={14} />}
            placeholder="Поиск по названию и артикулу…"
            value={searchLocal}
            onChange={e => setSearchLocal(e.target.value)}
          />
        </div>

        <ActiveFilters />

        {(treeError || productsError) && !data?.pages.length && !categoryTree?.length ? (
          <QueryError
            message={parseApiError(treeError ? treeErr : productsErr, 'Не удалось загрузить каталог')}
            onRetry={() => {
              if (treeError) refetchTree()
              else refetchProducts()
            }}
          />
        ) : isLoading ? (
          <div className="flex justify-center py-20"><Spinner /></div>
        ) : products.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-24 text-center">
            <Search size={40} strokeWidth={1.5} className="text-scout-dim" />
            <p className="text-base text-scout-text">Ничего не найдено</p>
            <p className="text-xs text-scout-muted">Попробуй изменить фильтры или сбросить</p>
            {f.isAnyActive && (
              <button
                onClick={f.resetAll}
                className="mt-2 rounded-scout border border-scout-subtle bg-scout-elevated px-4 py-2 text-xs text-scout-text transition-colors hover:border-scout-accent/60 hover:text-scout-accent"
              >
                Сбросить фильтры
              </button>
            )}
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
