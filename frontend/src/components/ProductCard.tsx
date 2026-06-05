import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ExternalLink, Package, Heart, BookmarkPlus } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { discount, formatPrice, getOfferOldPrice, getOfferPrice, resolveProductImageCandidates } from '@/lib/utils'
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
  const [imageIndex, setImageIndex] = useState(0)
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
  const price = getOfferPrice(offer)
  const oldPrice = getOfferOldPrice(offer)
  const hasDiscount = price !== null && oldPrice !== null && oldPrice > price
  const imageCandidates = resolveProductImageCandidates(product)
  const imageSrc = imageCandidates[imageIndex] ?? null

  useEffect(() => {
    setImageIndex(0)
  }, [product.id, product.image_url, offer?.image_url, imageCandidates.length])

  return (
    <div className="group flex flex-col bg-scout-elevated border border-scout-subtle rounded-scout-lg overflow-hidden transition-all duration-200 hover:border-scout-border hover:-translate-y-0.5">
      <Link to={`/products/${product.id}`} className="block bg-scout-bg">
        <div className="flex h-36 items-center justify-center">
          {imageSrc ? (
            <img
              src={imageSrc}
              alt={product.name}
              className="h-full w-full object-contain p-3"
              onError={() => setImageIndex(prev => prev + 1)}
            />
          ) : (
            <Package size={40} className="text-scout-subtle" strokeWidth={1.5} />
          )}
        </div>
      </Link>

      <div className="flex flex-1 flex-col gap-2 p-4">
        {product.brand && (
          <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-scout-dim">
            {product.brand}
          </span>
        )}
        <Link
          to={`/products/${product.id}`}
          className="line-clamp-2 text-[13px] font-semibold text-scout-text transition-colors hover:text-scout-accent min-h-[40px]"
        >
          {product.name}
        </Link>

        <div className="mt-auto pt-3 border-t border-scout-subtle flex items-end justify-between gap-2">
          {offer ? (
            <div className="flex flex-col gap-1">
              {oldPrice !== null && (
                <span className="text-[11px] text-scout-dim line-through leading-none scout-tabnums">
                  {formatPrice(oldPrice)}
                </span>
              )}
              <div className="flex items-baseline gap-2">
                <span className="text-[16px] font-bold text-scout-accent leading-none scout-tabnums">
                  {formatPrice(price)}
                </span>
                {hasDiscount && (
                  <span className="text-[11px] font-bold text-scout-success scout-tabnums">
                    -{discount(price, oldPrice)}%
                  </span>
                )}
              </div>
            </div>
          ) : (
            <span className="text-xs text-scout-dim">Нет в наличии</span>
          )}

          <div className="flex shrink-0 items-center gap-1">
            {offer?.url && (
              <a
                href={offer.url}
                target="_blank"
                rel="noopener noreferrer"
                title="Открыть в магазине"
                className="p-1.5 text-scout-dim transition-colors hover:bg-scout-subtle hover:text-scout-accent rounded-scout"
              >
                <ExternalLink size={14} />
              </a>
            )}

            <CompareCheckbox
              productId={product.id}
              category={{ id: product.category.id, name: product.category.name }}
            />

            <button
              onClick={e => { e.preventDefault(); toggleWishlist.mutate({ remove: inWishlist, itemId: wishlistItemId }) }}
              disabled={toggleWishlist.isPending}
              title={inWishlist ? 'Удалить из вишлиста' : 'В вишлист'}
              className="p-1.5 transition-colors hover:bg-scout-subtle disabled:opacity-50 rounded-scout"
            >
              <Heart
                size={14}
                className={inWishlist ? 'fill-scout-accent text-scout-accent' : 'text-scout-dim'}
              />
            </button>

            {onSubscribe && (
              <button
                onClick={() => onSubscribe(product)}
                title={subscribed ? 'В подписках' : 'Добавить в подписки'}
                className="p-1.5 transition-colors hover:bg-scout-subtle rounded-scout"
              >
                <BookmarkPlus size={14} className={subscribed ? 'text-scout-accent' : 'text-scout-dim'} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
