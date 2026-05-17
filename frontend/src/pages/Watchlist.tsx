import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { BookMarked, Plus, Target, TrendingDown, AlertCircle } from 'lucide-react'
import { SubscriptionCard } from '@/components/SubscriptionCard'
import { AddSubscriptionModal } from '@/components/AddSubscriptionModal'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { PageSpinner } from '@/components/ui/Spinner'
import { Card } from '@/components/ui/Card'
import { subscriptionsApi } from '@/api/subscriptions'
import { useToast } from '@/components/ui/Toast'
import { formatPrice } from '@/lib/utils'

type Filter = 'all' | 'reached' | 'active'

export default function Watchlist() {
  const [addOpen, setAddOpen] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const qc = useQueryClient()
  const { toast } = useToast()

  const { data, isLoading } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: subscriptionsApi.list,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => subscriptionsApi.delete(id),
    onMutate: (id) => setDeletingId(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subscriptions'] })
      toast('Подписка удалена', 'info')
    },
    onError: () => toast('Ошибка при удалении', 'error'),
    onSettled: () => setDeletingId(null),
  })

  const subs = data?.results ?? []

  const filtered = subs.filter(s => {
    if (filter === 'all') return true
    const cur = s.product.best_offer?.price ?? null
    if (filter === 'reached') return cur !== null && cur <= s.target_price
    if (filter === 'active') return cur === null || cur > s.target_price
    return true
  })

  const reachedCount = subs.filter(s => {
    const cur = s.product.best_offer?.price ?? null
    return cur !== null && cur <= s.target_price
  }).length

  const totalTarget = subs.reduce((acc, s) => acc + s.target_price, 0)

  return (
    <>
      <div className="mb-8 flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <motion.div
            className="flex items-center gap-3"
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <BookMarked size={28} className="text-brand-400" />
            <div>
              <h1 className="text-3xl font-bold text-white">Подписки</h1>
              <p className="text-sm text-white/50">Мониторинг целевых цен</p>
            </div>
          </motion.div>
          <Button onClick={() => setAddOpen(true)}>
            <Plus size={16} /> Добавить
          </Button>
        </div>

        {/* Stats */}
        {subs.length > 0 && (
          <motion.div
            className="grid grid-cols-2 gap-3 sm:grid-cols-3"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Card className="flex items-center gap-3 p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600/30">
                <BookMarked size={18} className="text-brand-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{subs.length}</p>
                <p className="text-xs text-white/50">Подписок</p>
              </div>
            </Card>

            <Card className="flex items-center gap-3 p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600/30">
                <TrendingDown size={18} className="text-emerald-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{reachedCount}</p>
                <p className="text-xs text-white/50">Достигли цели</p>
              </div>
            </Card>

            <Card className="col-span-2 flex items-center gap-3 p-4 sm:col-span-1">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-600/30">
                <Target size={18} className="text-purple-400" />
              </div>
              <div>
                <p className="text-lg font-bold text-white">{formatPrice(totalTarget)}</p>
                <p className="text-xs text-white/50">Сумма целей</p>
              </div>
            </Card>
          </motion.div>
        )}

        {/* Filters */}
        {subs.length > 0 && (
          <div className="flex gap-2">
            {([
              ['all',     'Все',           subs.length],
              ['reached', 'Достигнуто',    reachedCount],
              ['active',  'Ожидание',      subs.length - reachedCount],
            ] as [Filter, string, number][]).map(([val, label, count]) => (
              <button
                key={val}
                onClick={() => setFilter(val)}
                className={`flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-medium transition-all ${
                  filter === val
                    ? 'bg-brand-600/30 text-brand-300'
                    : 'text-white/50 hover:bg-white/10 hover:text-white'
                }`}
              >
                {label}
                <Badge variant={filter === val ? 'default' : 'ghost'} className="text-xs">
                  {count}
                </Badge>
              </button>
            ))}
          </div>
        )}
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : subs.length === 0 ? (
        <motion.div
          className="flex flex-col items-center gap-4 py-24 text-white/40"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <AlertCircle size={56} strokeWidth={1} />
          <p className="text-xl font-medium">Подписок пока нет</p>
          <p className="text-sm">Добавьте товар и укажите целевую цену — мы сообщим, когда цена снизится</p>
          <Button onClick={() => setAddOpen(true)} className="mt-2">
            <Plus size={16} /> Добавить первую подписку
          </Button>
        </motion.div>
      ) : (
        <div className="flex flex-col gap-3">
          <AnimatePresence>
            {filtered.map((sub, i) => (
              <SubscriptionCard
                key={sub.id}
                sub={sub}
                index={i}
                onDelete={id => deleteMutation.mutate(id)}
                deleting={deletingId === sub.id}
              />
            ))}
          </AnimatePresence>

          {filtered.length === 0 && (
            <div className="flex h-40 items-center justify-center text-sm text-white/40">
              Нет подписок в этой категории
            </div>
          )}
        </div>
      )}

      <AddSubscriptionModal open={addOpen} onClose={() => setAddOpen(false)} />
    </>
  )
}
