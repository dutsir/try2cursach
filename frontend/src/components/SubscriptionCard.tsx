import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Link } from 'react-router-dom'
import {
  Trash2, ChevronDown, ExternalLink, Target, TrendingDown, TrendingUp,
  Check, X, Pencil, Pause, Play,
} from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { PriceChart } from '@/components/PriceChart'
import { formatPrice, SOURCE_LABELS, SOURCE_COLORS, getOfferPrice } from '@/lib/utils'
import type { Subscription } from '@/types'

interface SubscriptionCardProps {
  sub: Subscription
  index?: number
  onDelete: (id: number) => void
  onUpdate?: (id: number, data: Partial<Pick<Subscription, 'target_price' | 'is_active'>>) => void
  deleting?: boolean
  updating?: boolean
}

export function SubscriptionCard({ sub, index = 0, onDelete, onUpdate, deleting, updating }: SubscriptionCardProps) {
  const [chartOpen, setChartOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [priceInput, setPriceInput] = useState(String(sub.target_price))
  const offer = sub.product.best_offer
  const currentPrice = getOfferPrice(offer)
  const paused = sub.is_active === false
  const diff = currentPrice !== null ? currentPrice - sub.target_price : null
  const reached = diff !== null && diff <= 0

  const saveTarget = () => {
    const v = parseFloat(priceInput)
    if (!onUpdate || !v || v <= 0) return
    if (v !== sub.target_price) onUpdate(sub.id, { target_price: v })
    setEditing(false)
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ delay: index * 0.04 }}
    >
      <Card className={paused ? 'overflow-hidden opacity-60' : 'overflow-hidden'}>
        <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start">
          {/* Info */}
          <div className="flex flex-1 flex-col gap-1 min-w-0">
            {sub.product.brand && (
              <span className="text-[10px] font-medium uppercase tracking-[0.1em] text-scout-dim">
                {sub.product.brand}
              </span>
            )}
            <Link
              to={`/products/${sub.product.id}`}
              className="truncate font-semibold text-scout-text hover:text-scout-accent transition-colors"
            >
              {sub.product.name}
            </Link>

            <div className="flex flex-wrap items-center gap-2 mt-1">
              {offer && (
                <Badge variant="ghost">
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ background: SOURCE_COLORS[offer.source] }}
                  />
                  {SOURCE_LABELS[offer.source] ?? offer.source}
                </Badge>
              )}
              {paused && <Badge variant="warning">Приостановлено</Badge>}

              {editing ? (
                <div className="flex items-center gap-1.5">
                  <Input
                    type="number"
                    value={priceInput}
                    onChange={e => setPriceInput(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') saveTarget(); if (e.key === 'Escape') setEditing(false) }}
                    autoFocus
                    className="h-7 w-28 text-sm"
                  />
                  <button
                    onClick={saveTarget}
                    title="Сохранить"
                    className="p-1 rounded-scout text-scout-success hover:bg-scout-success/15 transition-colors"
                  >
                    <Check size={14} />
                  </button>
                  <button
                    onClick={() => { setPriceInput(String(sub.target_price)); setEditing(false) }}
                    title="Отмена"
                    className="p-1 rounded-scout text-scout-muted hover:bg-scout-subtle transition-colors"
                  >
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => onUpdate && setEditing(true)}
                  disabled={!onUpdate}
                  title={onUpdate ? 'Изменить целевую цену' : undefined}
                  className="group/target inline-flex"
                >
                  <Badge variant={reached ? 'success' : 'default'}>
                    <Target size={10} />
                    Цель: {formatPrice(sub.target_price)}
                    {onUpdate && <Pencil size={9} className="ml-0.5 opacity-0 transition-opacity group-hover/target:opacity-70" />}
                  </Badge>
                </button>
              )}
            </div>
          </div>

          {/* Price */}
          <div className="flex shrink-0 flex-col items-end gap-2">
            {currentPrice !== null ? (
              <>
                <span className="text-xl font-bold text-scout-text scout-tabnums">{formatPrice(currentPrice)}</span>
                {diff !== null && (
                  <span className={`flex items-center gap-1 text-sm font-medium ${reached ? 'text-scout-success' : 'text-scout-danger'}`}>
                    {reached
                      ? <><TrendingDown size={14} /> Достигнуто!</>
                      : <><TrendingUp size={14} /> +{formatPrice(Math.abs(diff))}</>
                    }
                  </span>
                )}
              </>
            ) : (
              <span className="text-sm text-scout-dim">Нет данных</span>
            )}
          </div>
        </div>

        {/* Actions bar */}
        <div className="flex items-center justify-between border-t border-scout-subtle px-5 py-3">
          <div className="flex gap-2">
            {offer?.url && (
              <a
                href={offer.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-xs text-scout-dim hover:text-scout-text transition-colors"
              >
                <ExternalLink size={13} /> Открыть в магазине
              </a>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setChartOpen(v => !v)}
              className="flex items-center gap-1.5 text-xs text-scout-dim hover:text-scout-text transition-colors"
            >
              График
              <motion.span animate={{ rotate: chartOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronDown size={13} />
              </motion.span>
            </button>
            {onUpdate && (
              <button
                onClick={() => onUpdate(sub.id, { is_active: paused })}
                disabled={updating}
                title={paused ? 'Возобновить мониторинг' : 'Приостановить мониторинг'}
                className="flex items-center gap-1.5 text-xs text-scout-dim hover:text-scout-text transition-colors disabled:opacity-50"
              >
                {paused ? <Play size={13} /> : <Pause size={13} />}
                {paused ? 'Возобновить' : 'Пауза'}
              </button>
            )}
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
              <div className="border-t border-scout-subtle px-5 py-4">
                <PriceChart productId={sub.product.id} targetPrice={sub.target_price} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </motion.div>
  )
}
