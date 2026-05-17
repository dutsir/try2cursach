import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { ExternalLink, BookmarkPlus, TrendingDown, Package } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { formatPrice, discount, SOURCE_LABELS } from '@/lib/utils'
import type { Product } from '@/types'

interface ProductCardProps {
  product: Product
  index?: number
  onSubscribe?: (product: Product) => void
  subscribed?: boolean
}

export function ProductCard({ product, index = 0, onSubscribe, subscribed }: ProductCardProps) {
  const offer = product.best_offer

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.35 }}
    >
      <Card hover className="flex flex-col gap-4 p-5">
        {/* Image placeholder */}
        <Link to={`/products/${product.id}`} className="block">
          <div className="flex h-36 items-center justify-center rounded-xl bg-white/5">
            {offer?.image_url ? (
              <img
                src={offer.image_url}
                alt={product.name}
                className="h-full w-full rounded-xl object-contain p-2"
              />
            ) : (
              <Package size={40} className="text-white/20" />
            )}
          </div>
        </Link>

        {/* Meta */}
        <div className="flex flex-col gap-1">
          {product.brand && (
            <span className="text-xs font-medium uppercase tracking-wider text-white/40">
              {product.brand}
            </span>
          )}
          <Link
            to={`/products/${product.id}`}
            className="line-clamp-2 text-sm font-semibold text-white transition hover:text-brand-300"
          >
            {product.name}
          </Link>
        </div>

        {/* Price block */}
        <div className="mt-auto flex items-end justify-between gap-2">
          {offer ? (
            <div>
              <div className="flex items-baseline gap-2">
                <span className="text-xl font-bold text-white">{formatPrice(offer.price)}</span>
                {offer.old_price && (
                  <span className="text-sm text-white/40 line-through">{formatPrice(offer.old_price)}</span>
                )}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="ghost">{SOURCE_LABELS[offer.source] ?? offer.source}</Badge>
                {offer.old_price && (
                  <Badge variant="success">
                    <TrendingDown size={10} />
                    -{discount(offer.price, offer.old_price)}%
                  </Badge>
                )}
              </div>
            </div>
          ) : (
            <span className="text-sm text-white/40">Нет в наличии</span>
          )}

          <div className="flex shrink-0 items-center gap-1">
            {offer?.url && (
              <a
                href={offer.url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg p-1.5 text-white/40 transition hover:bg-white/10 hover:text-white"
              >
                <ExternalLink size={15} />
              </a>
            )}
            {onSubscribe && (
              <Button
                size="icon"
                variant={subscribed ? 'secondary' : 'ghost'}
                onClick={() => onSubscribe(product)}
                title={subscribed ? 'В подписках' : 'Добавить в подписки'}
              >
                <BookmarkPlus size={15} className={subscribed ? 'text-brand-400' : ''} />
              </Button>
            )}
          </div>
        </div>
      </Card>
    </motion.div>
  )
}
