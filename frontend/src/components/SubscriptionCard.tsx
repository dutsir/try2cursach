import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Link } from 'react-router-dom'
import { Trash2, ChevronDown, ExternalLink, Target, TrendingDown, TrendingUp } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { PriceChart } from '@/components/PriceChart'
import { formatPrice, SOURCE_LABELS, SOURCE_COLORS } from '@/lib/utils'
import type { Subscription } from '@/types'

interface SubscriptionCardProps {
  sub: Subscription
  index?: number
  onDelete: (id: number) => void
  deleting?: boolean
}

export function SubscriptionCard({ sub, index = 0, onDelete, deleting }: SubscriptionCardProps) {
  const [chartOpen, setChartOpen] = useState(false)
  const offer = sub.product.best_offer
  const currentPrice = offer?.price ?? null
  const diff = currentPrice !== null ? currentPrice - sub.target_price : null
  const reached = diff !== null && diff <= 0

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ delay: index * 0.04 }}
    >
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start">
          {/* Info */}
          <div className="flex flex-1 flex-col gap-1 min-w-0">
            {sub.product.brand && (
              <span className="text-xs font-medium uppercase tracking-wider text-white/40">
                {sub.product.brand}
              </span>
            )}
            <Link
              to={`/products/${sub.product.id}`}
              className="truncate font-semibold text-white hover:text-brand-300 transition"
            >
              {sub.product.name}
            </Link>

            <div className="flex flex-wrap gap-2 mt-1">
              {offer && (
                <Badge variant="ghost">
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ background: SOURCE_COLORS[offer.source] }}
                  />
                  {SOURCE_LABELS[offer.source] ?? offer.source}
                </Badge>
              )}
              <Badge variant={reached ? 'success' : 'default'}>
                <Target size={10} />
                Цель: {formatPrice(sub.target_price)}
              </Badge>
            </div>
          </div>

          {/* Price */}
          <div className="flex shrink-0 flex-col items-end gap-2">
            {currentPrice !== null ? (
              <>
                <span className="text-xl font-bold text-white">{formatPrice(currentPrice)}</span>
                {diff !== null && (
                  <span className={`flex items-center gap-1 text-sm font-medium ${reached ? 'text-emerald-400' : 'text-red-400'}`}>
                    {reached
                      ? <><TrendingDown size={14} /> Достигнуто!</>
                      : <><TrendingUp size={14} /> +{formatPrice(Math.abs(diff))}</>
                    }
                  </span>
                )}
              </>
            ) : (
              <span className="text-sm text-white/40">Нет данных</span>
            )}
          </div>
        </div>

        {/* Actions bar */}
        <div className="flex items-center justify-between border-t border-white/10 px-5 py-3">
          <div className="flex gap-2">
            {offer?.url && (
              <a
                href={offer.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-xs text-white/50 hover:text-white transition"
              >
                <ExternalLink size={13} /> Открыть в магазине
              </a>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setChartOpen(v => !v)}
              className="flex items-center gap-1.5 text-xs text-white/50 hover:text-white transition"
            >
              График
              <motion.span animate={{ rotate: chartOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronDown size={13} />
              </motion.span>
            </button>
            <Button
              size="sm"
              variant="danger"
              loading={deleting}
              onClick={() => onDelete(sub.id)}
            >
              <Trash2 size={13} />
            </Button>
          </div>
        </div>

        {/* Price chart accordion */}
        <AnimatePresence>
          {chartOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="overflow-hidden"
            >
              <div className="border-t border-white/10 px-5 py-4">
                <PriceChart productId={sub.product.id} targetPrice={sub.target_price} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </motion.div>
  )
}
