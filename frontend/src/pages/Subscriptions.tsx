import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence } from 'framer-motion'
import { Plus } from 'lucide-react'
import { SubscriptionCard } from '@/components/SubscriptionCard'
import { AddSubscriptionModal } from '@/components/AddSubscriptionModal'
import { Button } from '@/components/ui/Button'
import { PageSpinner } from '@/components/ui/Spinner'
import { subscriptionsApi } from '@/api/subscriptions'
import { useToast } from '@/components/ui/Toast'
import { formatPrice } from '@/lib/utils'
import type { Subscription } from '@/types'

type Filter = 'all' | 'reached' | 'active' | 'paused'

export default function Subscriptions() {
  const [addOpen, setAddOpen] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [updatingId, setUpdatingId] = useState<number | null>(null)
  const qc = useQueryClient()
  const { toast } = useToast()

  const { data, isLoading } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: subscriptionsApi.list,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => subscriptionsApi.delete(id),
    onMutate: id => setDeletingId(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subscriptions'] })
      toast('Подписка удалена', 'info')
    },
    onError: () => toast('Ошибка при удалении', 'error'),
    onSettled: () => setDeletingId(null),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Pick<Subscription, 'target_price' | 'is_active'>> }) =>
      subscriptionsApi.update(id, data),
    onMutate: ({ id }) => setUpdatingId(id),
    onSuccess: (_res, { data }) => {
      qc.invalidateQueries({ queryKey: ['subscriptions'] })
      toast(
        'is_active' in data
          ? (data.is_active ? 'Мониторинг возобновлён' : 'Мониторинг приостановлен')
          : 'Целевая цена обновлена',
        'success',
      )
    },
    onError: () => toast('Не удалось обновить подписку', 'error'),
    onSettled: () => setUpdatingId(null),
  })

  const subs = data?.results ?? []

  const isReached = (s: Subscription) => {
    const cur = s.product.best_offer?.price ?? null
    return cur !== null && cur <= s.target_price
  }

  const filtered = subs.filter(s => {
    if (filter === 'all') return true
    if (filter === 'paused') return s.is_active === false
    if (filter === 'reached') return s.is_active !== false && isReached(s)
    if (filter === 'active') return s.is_active !== false && !isReached(s)
    return true
  })

  const reachedCount = subs.filter(s => s.is_active !== false && isReached(s)).length
  const pausedCount = subs.filter(s => s.is_active === false).length
  const activeCount = subs.length - pausedCount - reachedCount
  const totalTarget = subs.reduce((acc, s) => acc + s.target_price, 0)

  return (
    <>
      <div className="mb-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="scout-caption">subscriptions</div>
            <h1 className="mt-1 font-display text-2xl lowercase tracking-tight text-scout-text">подписки на цену</h1>
          </div>
          <Button variant="green" onClick={() => setAddOpen(true)}>
            <Plus size={14} /> Добавить
          </Button>
        </div>
        <div className="h-px bg-scout-border mt-3" />

        {subs.length > 0 && (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="bg-scout-elevated border border-scout-border rounded-scout p-3">
              <p className="text-[10px] uppercase tracking-wider text-scout-muted">Подписок</p>
              <p className="text-xl font-bold text-scout-text mt-1 scout-tabnums">{subs.length}</p>
            </div>
            <div className="bg-scout-elevated border border-scout-border rounded-scout p-3">
              <p className="text-[10px] uppercase tracking-wider text-scout-muted">Достигли цели</p>
              <p className="text-xl font-bold text-scout-success mt-1 scout-tabnums">{reachedCount}</p>
            </div>
            <div className="bg-scout-elevated border border-scout-border rounded-scout p-3">
              <p className="text-[10px] uppercase tracking-wider text-scout-muted">На паузе</p>
              <p className="text-xl font-bold text-scout-warning mt-1 scout-tabnums">{pausedCount}</p>
            </div>
            <div className="bg-scout-elevated border border-scout-border rounded-scout p-3">
              <p className="text-[10px] uppercase tracking-wider text-scout-muted">Сумма целей</p>
              <p className="text-xl font-bold text-scout-text mt-1 scout-tabnums">{formatPrice(totalTarget)}</p>
            </div>
          </div>
        )}

        {subs.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {([
              ['all', 'Все', subs.length],
              ['reached', 'Достигнуто', reachedCount],
              ['active', 'Ожидание', activeCount],
              ['paused', 'На паузе', pausedCount],
            ] as [Filter, string, number][]).map(([val, label, count]) => (
              <button
                key={val}
                onClick={() => setFilter(val)}
                className={`flex items-center gap-2 rounded-scout px-3 py-1.5 text-sm font-medium transition-colors ${
                  filter === val
                    ? 'bg-scout-subtle text-scout-text'
                    : 'text-scout-muted hover:bg-scout-subtle/60 hover:text-scout-text'
                }`}
              >
                {label}
                <span className="text-[11px] text-scout-dim scout-tabnums">{count}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : subs.length === 0 ? (
        <div className="bg-scout-elevated border border-scout-border rounded-scout py-16 flex flex-col items-center gap-3 text-scout-muted">
          <p className="text-base text-scout-text">Подписок пока нет</p>
          <p className="text-xs">Укажите целевую цену — мы сообщим, когда товар подешевеет</p>
          <Button variant="green" className="mt-2" onClick={() => setAddOpen(true)}>
            <Plus size={14} /> Добавить первую подписку
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <AnimatePresence>
            {filtered.map((sub, i) => (
              <SubscriptionCard
                key={sub.id}
                sub={sub}
                index={i}
                onDelete={id => deleteMutation.mutate(id)}
                onUpdate={(id, d) => updateMutation.mutate({ id, data: d })}
                deleting={deletingId === sub.id}
                updating={updatingId === sub.id}
              />
            ))}
          </AnimatePresence>

          {filtered.length === 0 && (
            <div className="flex h-40 items-center justify-center text-sm text-scout-dim">
              Нет подписок в этой категории
            </div>
          )}
        </div>
      )}

      <AddSubscriptionModal open={addOpen} onClose={() => setAddOpen(false)} />
    </>
  )
}
