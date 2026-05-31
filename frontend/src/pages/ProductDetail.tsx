import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { ArrowLeft, ExternalLink, Package, ShoppingCart, BookmarkPlus } from 'lucide-react'
import { PriceChart } from '@/components/PriceChart'
import { PriceWindowStats } from '@/components/PriceWindowStats'
import { AddSubscriptionModal } from '@/components/AddSubscriptionModal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { PageSpinner } from '@/components/ui/Spinner'
import { productsApi } from '@/api/products'
import { subscriptionsApi } from '@/api/subscriptions'
import { formatPrice, formatRelativeDate, SOURCE_LABELS, SOURCE_COLORS, discount, cn } from '@/lib/utils'
import type { PriceWindow } from '@/types'

export default function ProductDetail() {
  const { id } = useParams<{ id: string }>()
  const productId = Number(id)
  const [subscribeOpen, setSubscribeOpen] = useState(false)
  const [priceWindow, setPriceWindow] = useState<PriceWindow>('30d')

  const { data: product, isLoading } = useQuery({
    queryKey: ['product', productId],
    queryFn: () => productsApi.detail(productId),
    enabled: !!productId,
  })

  const { data: priceStats } = useQuery({
    queryKey: ['price-stats', productId],
    queryFn: () => productsApi.priceStats(productId),
    enabled: !!productId,
  })

  const { data: subs } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: subscriptionsApi.list,
  })

  const isSubscribed = subs?.results.some(s => s.product.id === productId) ?? false
  const subscription = subs?.results.find(s => s.product.id === productId)

  if (isLoading) return <PageSpinner />
  if (!product) return (
    <div className="flex flex-col items-center gap-4 py-24 text-scout-dim">
      <Package size={56} strokeWidth={1} />
      <p className="text-xl">Товар не найден</p>
      <Link to="/" className="text-scout-accent hover:underline">← Вернуться в каталог</Link>
    </div>
  )

  const bestOffer = product.best_offer ?? product.offers?.[0]

  return (
    <>
      {/* Breadcrumb */}
      <Link to="/" className="mb-6 inline-flex items-center gap-2 text-sm text-scout-muted hover:text-scout-text transition">
        <ArrowLeft size={15} /> Каталог
      </Link>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Left col */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Hero card */}
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
            <Card className="p-6">
              <div className="flex flex-col gap-6 sm:flex-row">
                {/* Image */}
                <div className="flex h-48 w-full items-center justify-center rounded-scout-lg bg-scout-bg sm:w-48 sm:shrink-0">
                  {bestOffer?.image_url ? (
                    <img
                      src={bestOffer.image_url}
                      alt={product.name}
                      className="h-full w-full rounded-scout-lg object-contain p-3"
                    />
                  ) : (
                    <Package size={56} className="text-scout-dim" />
                  )}
                </div>

                {/* Info */}
                <div className="flex flex-1 flex-col gap-3">
                  {product.brand && (
                    <span className="text-xs font-semibold uppercase tracking-widest text-scout-accent">
                      {product.brand}
                    </span>
                  )}
                  <h1 className="text-2xl font-bold leading-snug text-scout-text">{product.name}</h1>

                  <div className="flex flex-wrap gap-2">
                    {product.vendor_code && (
                      <Badge variant="ghost">Арт. {product.vendor_code}</Badge>
                    )}
                    {product.category && (
                      <Badge variant="ghost">{product.category.name}</Badge>
                    )}
                    {!product.is_active && (
                      <Badge variant="danger">Снят с продажи</Badge>
                    )}
                  </div>

                  {bestOffer && (
                    <div className="mt-auto flex flex-wrap items-center gap-3">
                      <span className="text-3xl font-bold text-scout-text">{formatPrice(bestOffer.current_price ?? bestOffer.price)}</span>
                      {bestOffer.old_price && (
                        <>
                          <span className="text-lg text-scout-dim line-through">{formatPrice(bestOffer.old_price)}</span>
                          {bestOffer.price && bestOffer.old_price && (
                            <Badge variant="success">-{discount(
                              typeof bestOffer.price === 'string' ? parseFloat(bestOffer.price) : bestOffer.price,
                              typeof bestOffer.old_price === 'string' ? parseFloat(bestOffer.old_price) : bestOffer.old_price
                            )}%</Badge>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          </motion.div>

          {/* Price chart */}
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <Card className="p-6">
              <div className="mb-4 flex items-center justify-between gap-3 flex-wrap">
                <h2 className="text-lg font-semibold text-scout-text">История цен</h2>
                {/* Переключатель окна */}
                <div className="inline-flex rounded-scout-lg border border-scout-subtle bg-scout-bg p-1">
                  {(['7d', '30d', 'all'] as PriceWindow[]).map(w => (
                    <button
                      key={w}
                      onClick={() => setPriceWindow(w)}
                      className={cn(
                        'rounded-lg px-3 py-1.5 text-xs font-medium transition',
                        priceWindow === w
                          ? 'bg-scout-accent text-scout-text'
                          : 'text-scout-muted hover:text-scout-text',
                      )}
                    >
                      {w === '7d' ? '7 дней' : w === '30d' ? '30 дней' : 'Всё время'}
                    </button>
                  ))}
                </div>
              </div>

              <PriceChart
                productId={productId}
                targetPrice={subscription?.target_price}
                window={priceWindow}
                stats={priceStats}
              />

              {/* Карточки метрик + bar-chart дневных средних */}
              <div className="mt-6">
                <PriceWindowStats
                  productId={productId}
                  stats={priceStats}
                  window={priceWindow}
                />
              </div>

              {/* Подсказки про линии */}
              <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-scout-dim">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-0.5 w-4 bg-scout-accent" /> средняя
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-scout-success" /> минимум
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-scout-danger" /> максимум
                </span>
                {subscription && (
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-0.5 w-4 bg-scout-success" /> цель {formatPrice(subscription.target_price)}
                  </span>
                )}
              </div>
            </Card>
          </motion.div>

          {/* Offers table */}
          {product.offers && product.offers.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
              <Card className="p-6">
                <h2 className="mb-4 text-lg font-semibold text-scout-text">Цены в магазинах</h2>
                <div className="flex flex-col divide-y divide-white/10">
                  {product.offers.map(offer => (
                    <div key={offer.id} className="flex items-center gap-4 py-3 first:pt-0 last:pb-0">
                      <span
                        className="flex h-2 w-2 shrink-0 rounded-full"
                        style={{ background: SOURCE_COLORS[offer.source] }}
                      />
                      <span className="flex-1 font-medium text-scout-text">
                        {SOURCE_LABELS[offer.source] ?? offer.source}
                      </span>

                      {offer.is_available ? (
                        <Badge variant="success">В наличии</Badge>
                      ) : (
                        <Badge variant="danger">Нет в наличии</Badge>
                      )}

                      <div className="text-right">
                        <p className="font-semibold text-scout-text">{offer.current_price ? formatPrice(offer.current_price) : 'не число ₽'}</p>
                        {offer.old_price && (
                          <p className="text-xs text-scout-dim line-through">{formatPrice(offer.old_price)}</p>
                        )}
                      </div>

                      <a
                        href={offer.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-2 text-scout-dim hover:text-scout-text transition"
                      >
                        <ExternalLink size={15} />
                      </a>
                    </div>
                  ))}
                </div>
              </Card>
            </motion.div>
          )}
        </div>

        {/* Right col */}
        <div className="flex flex-col gap-4">
          {/* Action card */}
          <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 }}>
            <Card className="p-6 flex flex-col gap-4">
              <h2 className="font-semibold text-scout-text">Действия</h2>

              {bestOffer && (
                <a
                  href={bestOffer.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex w-full items-center justify-center gap-2 rounded-scout-lg bg-scout-accent py-3 font-medium text-scout-text transition hover:bg-scout-accent-hover"
                >
                  <ShoppingCart size={16} />
                  Купить в {SOURCE_LABELS[bestOffer.source]}
                </a>
              )}

              <Button
                variant={isSubscribed ? 'secondary' : 'ghost'}
                className="w-full"
                onClick={() => setSubscribeOpen(true)}
              >
                <BookmarkPlus size={16} />
                {isSubscribed ? 'Изменить подписку' : 'Следить за ценой'}
              </Button>

              {isSubscribed && subscription && (
                <div className="rounded-scout-lg bg-scout-accent/10 px-4 py-3 text-sm">
                  <p className="text-scout-muted">Ваша целевая цена:</p>
                  <p className="text-lg font-bold text-scout-accent">{formatPrice(subscription.target_price)}</p>
                </div>
              )}
            </Card>
          </motion.div>

          {/* Last updated */}
          {product.last_parsed_at && (
            <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
              <Card className="px-5 py-4">
                <p className="text-xs text-scout-dim">
                  Обновлено {formatRelativeDate(product.last_parsed_at)}
                </p>
              </Card>
            </motion.div>
          )}
        </div>
      </div>

      <AddSubscriptionModal
        open={subscribeOpen}
        onClose={() => setSubscribeOpen(false)}
        preselectedProduct={product}
      />
    </>
  )
}
