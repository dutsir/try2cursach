import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ExternalLink, Package, Heart, BookmarkPlus } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { formatPrice, discount, SOURCE_LABELS } from '@/lib/utils'
import { wishlistApi } from '@/api/wishlist'
import { CompareCheckbox } from './CompareCheckbox'
import type { Product } from '@/types'

interface ProductCardProps {
  product: Product
  index?: number
  onSubscribe?: (product: Product) => void
  subscribed?: boolean
  wishlistItemId?: number | null
}

export function ProductCard({ product, onSubscribe, subscribed, wishlistItemId }: ProductCardProps) {
  const [optimisticInWishlist, setOptimisticInWishlist] = useState<boolean | null>(null)
  const qc = useQueryClient()

  const inWishlist = optimisticInWishlist ?? wishlistItemId != null

  const toggleWishlist = useMutation({
    mutationFn: ({ remove, itemId }: { remove: boolean; itemId: number | null | undefined }) =>
      remove && itemId != null
        ? wishlistApi.removeItem(itemId)
        : wishlistApi.addItem(product.id),
    onMutate: ({ remove }) => setOptimisticInWishlist(!remove),
    onSuccess: () => {
      setOptimisticInWishlist(null)
      qc.invalidateQueries({ queryKey: ['wishlist'] })
    },
    onError: () => setOptimisticInWishlist(null),
  })

  const offer = product.best_offer

  return (
    <div className="group flex flex-col bg-steam-card border border-steam-border rounded-steam overflow-hidden transition-colors duration-100 hover:border-steam-blue/60">
      <Link to={`/products/${product.id}`} className="block bg-steam-darker">
        <div className="flex h-36 items-center justify-center">
          {offer?.image_url ? (
            <img
              src={offer.image_url}
              alt={product.name}
              className="h-full w-full object-contain p-3"
            />
          ) : (
            <Package size={40} className="text-steam-border" strokeWidth={1.5} />
          )}
        </div>
      </Link>

      <div className="flex flex-1 flex-col gap-2 p-3">
        {product.brand && (
          <span className="text-[10px] font-semibold uppercase tracking-wider text-steam-muted">
            {product.brand}
          </span>
        )}
        <Link
          to={`/products/${product.id}`}
          className="line-clamp-2 text-sm font-semibold text-steam-light transition-colors hover:text-steam-blue min-h-[40px]"
        >
          {product.name}
        </Link>

        <div className="mt-auto pt-2 border-t border-steam-border/60 flex items-end justify-between gap-2">
          {offer ? (
            <div className="flex flex-col gap-1">
              {offer.old_price && (
                <span className="text-[11px] text-steam-muted line-through leading-none">
                  {formatPrice(offer.old_price)}
                </span>
              )}
              <div className="flex items-baseline gap-2">
                <span className="text-base font-bold text-steam-green leading-none">
                  {formatPrice(offer.price)}
                </span>
                {offer.old_price && (
                  <span className="text-[11px] font-bold text-steam-green">
                    -{discount(offer.price, offer.old_price)}%
                  </span>
                )}
              </div>
              <span className="text-[10px] uppercase tracking-wide text-steam-muted">
                {SOURCE_LABELS[offer.source] ?? offer.source}
              </span>
            </div>
          ) : (
            <span className="text-xs text-steam-muted">Нет в наличии</span>
          )}

          <div className="flex shrink-0 items-center gap-1">
            {offer?.url && (
              <a
                href={offer.url}
                target="_blank"
                rel="noopener noreferrer"
                title="Открыть в магазине"
                className="p-1.5 text-steam-muted transition-colors hover:bg-steam-panel hover:text-steam-blue rounded-steam"
              >
                <ExternalLink size={14} />
              </a>
            )}

            <CompareCheckbox productId={product.id} />

            <button
              onClick={e => { e.preventDefault(); toggleWishlist.mutate({ remove: inWishlist, itemId: wishlistItemId }) }}
              disabled={toggleWishlist.isPending}
              title={inWishlist ? 'Удалить из вишлиста' : 'В вишлист'}
              className="p-1.5 transition-colors hover:bg-steam-panel disabled:opacity-50 rounded-steam"
            >
              <Heart
                size={14}
                className={inWishlist ? 'fill-steam-blue text-steam-blue' : 'text-steam-muted'}
              />
            </button>

            {onSubscribe && (
              <button
                onClick={() => onSubscribe(product)}
                title={subscribed ? 'В подписках' : 'Добавить в подписки'}
                className="p-1.5 transition-colors hover:bg-steam-panel rounded-steam"
              >
                <BookmarkPlus size={14} className={subscribed ? 'text-steam-blue' : 'text-steam-muted'} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
