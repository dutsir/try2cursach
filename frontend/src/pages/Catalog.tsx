import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, SlidersHorizontal, ChevronDown } from 'lucide-react'
import { motion } from 'framer-motion'
import { ProductCard } from '@/components/ProductCard'
import { AddSubscriptionModal } from '@/components/AddSubscriptionModal'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { PageSpinner } from '@/components/ui/Spinner'
import { productsApi } from '@/api/products'
import { subscriptionsApi } from '@/api/subscriptions'
import { useDebounce } from '@/hooks/useDebounce'
import type { Product } from '@/types'

const ORDERINGS = [
  { value: '',         label: 'По умолчанию' },
  { value: 'name',     label: 'Название А–Я' },
  { value: '-name',    label: 'Название Я–А' },
]

const SOURCES = ['', 'dns', 'citilink', 'ozon']
const SOURCE_LABELS: Record<string, string> = { '': 'Все магазины', dns: 'DNS', citilink: 'Ситилинк', ozon: 'Ozon' }

export default function Catalog() {
  const [search, setSearch] = useState('')
  const [ordering, setOrdering] = useState('')
  const [source, setSource] = useState('')
  const [page, setPage] = useState(1)
  const [subscribeTarget, setSubscribeTarget] = useState<Product | null>(null)

  const debouncedSearch = useDebounce(search, 400)

  const { data, isLoading } = useQuery({
    queryKey: ['products', debouncedSearch, ordering, source, page],
    queryFn: () => productsApi.list({ search: debouncedSearch, ordering, source, page, page_size: 24 }),
  })

  const { data: subs } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: subscriptionsApi.list,
  })
  const subscribedIds = new Set(subs?.results.map(s => s.product.id) ?? [])

  return (
    <>
      {/* Toolbar */}
      <div className="mb-8 flex flex-col gap-4">
        <motion.h1
          className="text-3xl font-bold text-white"
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
        >
          Каталог товаров
        </motion.h1>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[200px]">
            <Input
              icon={<Search size={15} />}
              placeholder="Поиск по названию, бренду..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
            />
          </div>

          {/* Source filter */}
          <div className="relative">
            <select
              value={source}
              onChange={e => { setSource(e.target.value); setPage(1) }}
              className="appearance-none rounded-xl border border-white/15 bg-white/10 px-4 py-2.5 pr-8 text-sm text-white focus:outline-none focus:ring-2 focus:ring-brand-500/30"
            >
              {SOURCES.map(s => (
                <option key={s} value={s} className="bg-slate-900">{SOURCE_LABELS[s]}</option>
              ))}
            </select>
            <ChevronDown size={14} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-white/40" />
          </div>

          {/* Ordering */}
          <div className="relative">
            <select
              value={ordering}
              onChange={e => setOrdering(e.target.value)}
              className="appearance-none rounded-xl border border-white/15 bg-white/10 px-4 py-2.5 pr-8 text-sm text-white focus:outline-none focus:ring-2 focus:ring-brand-500/30"
            >
              {ORDERINGS.map(o => (
                <option key={o.value} value={o.value} className="bg-slate-900">{o.label}</option>
              ))}
            </select>
            <SlidersHorizontal size={14} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-white/40" />
          </div>
        </div>

        {data && (
          <p className="text-sm text-white/40">
            Найдено: <span className="text-white">{data.count}</span> товаров
          </p>
        )}
      </div>

      {/* Grid */}
      {isLoading ? (
        <PageSpinner />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {data?.results.map((product, i) => (
              <ProductCard
                key={product.id}
                product={product}
                index={i}
                onSubscribe={setSubscribeTarget}
                subscribed={subscribedIds.has(product.id)}
              />
            ))}
          </div>

          {data?.results.length === 0 && (
            <div className="flex flex-col items-center gap-3 py-24 text-white/40">
              <Search size={48} strokeWidth={1} />
              <p className="text-lg">Ничего не найдено</p>
              <p className="text-sm">Попробуйте изменить поиск или фильтры</p>
            </div>
          )}

          {/* Pagination */}
          {data && data.count > 24 && (
            <div className="mt-8 flex items-center justify-center gap-3">
              <Button
                variant="secondary"
                disabled={!data.previous}
                onClick={() => setPage(p => p - 1)}
              >
                Назад
              </Button>
              <span className="text-sm text-white/50">
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
