import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search, X, Loader2 } from 'lucide-react'
import { ImagePlaceholder } from './ImagePlaceholder'
import { MarketplaceTag } from './MarketplaceTag'
import { productsApi } from '@/api/products'
import { useDebounce } from '@/hooks/useDebounce'
import { formatPrice } from '@/lib/utils'

interface AddProductModalProps {
  onClose: () => void
}

export function AddProductModal({ onClose }: AddProductModalProps) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const debounced = useDebounce(query.trim(), 350)
  const active = debounced.length >= 2

  const { data, isFetching } = useQuery({
    queryKey: ['catalog-lookup', debounced],
    queryFn: () => productsApi.list({ search: debounced, page: 1, page_size: 8 }),
    enabled: active,
    staleTime: 60_000,
  })
  const results = data?.results ?? []
  const total = data?.count ?? 0

  function openProduct(id: number) {
    navigate(`/products/${id}`)
    onClose()
  }

  function openCatalog() {
    navigate(`/catalog?search=${encodeURIComponent(debounced)}`)
    onClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh] animate-fade-in"
      style={{ background: 'rgba(10,10,10,0.7)', backdropFilter: 'blur(8px)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-[600px] bg-scout-elevated border border-scout-border rounded-scout-xl p-8 shadow-[0_24px_80px_rgba(0,0,0,0.6)]"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="scout-caption">catalog</div>
            <h2 className="mt-1.5 font-display text-[32px] font-bold tracking-[-0.02em] lowercase text-scout-text">
              найти в каталоге
            </h2>
            <p className="mt-1.5 text-[13px] text-scout-muted max-w-[420px]">
              проверь, есть ли этот товар или его аналог — мы уже отслеживаем цены по нескольким магазинам.
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 shrink-0 rounded-scout text-scout-muted hover:bg-scout-subtle hover:text-scout-text border border-scout-subtle flex items-center justify-center transition-colors"
          >
            <X size={14} />
          </button>
        </div>

        <div className="mt-7">
          <div className="flex items-center gap-2 bg-scout-bg border border-scout-border rounded-scout px-3 h-12 focus-within:border-scout-accent/50 transition-colors">
            <Search size={15} className="text-scout-dim shrink-0" />
            <input
              autoFocus
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="название или артикул товара…"
              className="flex-1 bg-transparent outline-none border-none text-sm text-scout-text placeholder:text-scout-dim"
            />
            {isFetching && <Loader2 size={14} className="animate-spin text-scout-dim shrink-0" />}
          </div>
        </div>

        {active && (
          <div className="mt-5">
            {results.length > 0 ? (
              <>
                <div className="divide-y divide-scout-subtle border border-scout-subtle rounded-scout-lg overflow-hidden">
                  {results.map(p => {
                    const offer = p.best_offer
                    return (
                      <button
                        key={p.id}
                        onClick={() => openProduct(p.id)}
                        className="flex w-full items-center gap-3.5 p-3 text-left transition-colors hover:bg-scout-subtle/40"
                      >
                        <ImagePlaceholder
                          width={48}
                          height={48}
                          label="img"
                          src={offer?.image_url}
                          className="shrink-0"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="line-clamp-1 text-[13px] text-scout-text">
                            {p.brand && <span className="font-semibold uppercase mr-1.5 text-scout-muted">{p.brand}</span>}
                            {p.name}
                          </div>
                          <div className="mt-1 flex items-center gap-2">
                            {offer && <MarketplaceTag source={offer.source} />}
                            <span className="text-[11px] text-scout-dim">{p.category.name}</span>
                          </div>
                        </div>
                        {offer?.price != null && (
                          <span className="shrink-0 font-sans text-sm font-bold text-scout-accent scout-tabnums">
                            {formatPrice(offer.price)}
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>
                {total > results.length && (
                  <button
                    onClick={openCatalog}
                    className="mt-3 w-full rounded-scout border border-scout-subtle bg-scout-bg py-2.5 text-[12px] text-scout-muted transition-colors hover:border-scout-accent/50 hover:text-scout-accent"
                  >
                    показать все {total.toLocaleString('ru-RU')} в каталоге
                  </button>
                )}
              </>
            ) : !isFetching ? (
              <div className="flex flex-col items-center gap-2 rounded-scout-lg border border-dashed border-scout-subtle py-10 text-center">
                <Search size={28} strokeWidth={1.5} className="text-scout-dim" />
                <p className="text-sm text-scout-text">ничего не нашли</p>
                <p className="max-w-[320px] text-xs text-scout-muted">
                  такого товара пока нет в каталоге. попробуй изменить запрос или поискать аналог по названию.
                </p>
              </div>
            ) : null}
          </div>
        )}

        {!active && (
          <div className="mt-5 text-center text-xs text-scout-dim">
            введи хотя бы 2 символа, чтобы начать поиск.
          </div>
        )}
      </div>
    </div>
  )
}
