import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, CheckCircle } from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Spinner'
import { productsApi } from '@/api/products'
import { subscriptionsApi } from '@/api/subscriptions'
import { formatPrice, SOURCE_LABELS } from '@/lib/utils'
import { useDebounce } from '@/hooks/useDebounce'
import { useToast } from '@/components/ui/Toast'
import type { Product } from '@/types'

interface Props {
  open: boolean
  onClose: () => void
  preselectedProduct?: Product
}

export function AddSubscriptionModal({ open, onClose, preselectedProduct }: Props) {
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Product | null>(preselectedProduct ?? null)
  const [targetPrice, setTargetPrice] = useState(() =>
    preselectedProduct?.best_offer?.price
      ? String(Math.round(preselectedProduct.best_offer.price * 0.9))
      : ''
  )
  const debouncedQuery = useDebounce(query, 400)
  const qc = useQueryClient()
  const { toast } = useToast()

  const { data, isLoading } = useQuery({
    queryKey: ['products', 'search', debouncedQuery],
    queryFn: () => productsApi.list({ search: debouncedQuery, page_size: 8 }),
    enabled: debouncedQuery.length > 1,
  })

  const mutation = useMutation({
    mutationFn: () =>
      subscriptionsApi.create(selected!.id, parseFloat(targetPrice)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subscriptions'] })
      toast('Подписка добавлена', 'success')
      onClose()
      setQuery('')
      setSelected(null)
      setTargetPrice('')
    },
    onError: () => toast('Ошибка при создании подписки', 'error'),
  })

  const suggestedPrice = selected?.best_offer?.price
    ? String(Math.round(selected.best_offer.price * 0.9))
    : ''

  return (
    <Modal open={open} onClose={onClose} title="Добавить подписку на цену">
      <div className="flex flex-col gap-4">
        {!preselectedProduct && (
          <>
            <Input
              icon={<Search size={15} />}
              placeholder="Поиск товара..."
              value={query}
              onChange={e => { setQuery(e.target.value); setSelected(null) }}
            />

            {isLoading && (
              <div className="flex justify-center py-4">
                <Spinner size="sm" />
              </div>
            )}

            {data?.results && query.length > 1 && (
              <ul className="max-h-56 overflow-y-auto rounded-scout border border-scout-subtle bg-scout-bg">
                {data.results.map(product => (
                  <li key={product.id} className="border-b border-scout-subtle last:border-0">
                    <button
                      onClick={() => {
                        setSelected(product)
                        setQuery(product.name)
                        if (!targetPrice) setTargetPrice(suggestedPrice || '')
                      }}
                      className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-scout-subtle"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="truncate text-sm font-medium text-scout-text">{product.name}</p>
                        {product.brand && (
                          <p className="text-xs text-scout-dim">{product.brand}</p>
                        )}
                      </div>
                      {product.best_offer && (
                        <div className="flex shrink-0 flex-col items-end gap-1">
                          <span className="text-sm font-semibold text-scout-text scout-tabnums">
                            {formatPrice(product.best_offer.price)}
                          </span>
                          <Badge variant="ghost">
                            {SOURCE_LABELS[product.best_offer.source]}
                          </Badge>
                        </div>
                      )}
                    </button>
                  </li>
                ))}
                {data.results.length === 0 && (
                  <li className="px-4 py-6 text-center text-sm text-scout-dim">
                    Ничего не найдено
                  </li>
                )}
              </ul>
            )}
          </>
        )}

        {selected && (
          <div className="flex items-center gap-2 rounded-scout border border-scout-accent/30 bg-scout-accent/10 px-4 py-3">
            <CheckCircle size={16} className="shrink-0 text-scout-accent" />
            <span className="line-clamp-1 flex-1 text-sm text-scout-text">{selected.name}</span>
            {selected.best_offer && (
              <span className="shrink-0 text-sm text-scout-accent scout-tabnums">
                {formatPrice(selected.best_offer.price)}
              </span>
            )}
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <label className="scout-caption">Целевая цена (₽)</label>
          <Input
            type="number"
            placeholder={suggestedPrice ? `Напр. ${suggestedPrice}` : 'Введите цену...'}
            value={targetPrice}
            onChange={e => setTargetPrice(e.target.value)}
          />
          {selected?.best_offer && selected.best_offer.price && targetPrice && (
            <p className="text-xs text-scout-dim">
              Текущая цена: {formatPrice(selected.best_offer.price)} —{' '}
              скидка {Math.round((1 - parseFloat(targetPrice) / selected.best_offer.price) * 100)}%
            </p>
          )}
        </div>

        <Button
          className="mt-2 w-full"
          loading={mutation.isPending}
          disabled={!selected || !targetPrice || parseFloat(targetPrice) <= 0}
          onClick={() => mutation.mutate()}
        >
          Создать подписку
        </Button>
      </div>
    </Modal>
  )
}
