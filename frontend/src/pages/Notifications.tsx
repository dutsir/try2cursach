import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Bell, CheckCircle, Check, CheckCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { notificationsApi } from '@/api/subscriptions'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { PageSpinner } from '@/components/ui/Spinner'
import { formatRelativeDate } from '@/lib/utils'

export default function Notifications() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['notifications'],
    queryFn: notificationsApi.list,
  })

  const markRead = useMutation({
    mutationFn: (id: number) => notificationsApi.markRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
      qc.invalidateQueries({ queryKey: ['notifications-unread'] })
    },
  })

  const markAllRead = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
      qc.invalidateQueries({ queryKey: ['notifications-unread'] })
    },
  })

  const hasUnread = data?.results.some(n => !n.is_read) ?? false

  return (
    <>
      <motion.div
        className="mb-8 flex items-center justify-between gap-3"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center gap-3">
          <Bell size={28} className="text-scout-accent" />
          <div>
            <h1 className="text-3xl font-bold text-scout-text">Уведомления</h1>
            <p className="text-sm text-scout-muted">История оповещений</p>
          </div>
        </div>
        {hasUnread && (
          <Button
            variant="secondary"
            onClick={() => markAllRead.mutate()}
            loading={markAllRead.isPending}
          >
            <CheckCheck size={15} className="mr-1.5" />
            Прочитать все
          </Button>
        )}
      </motion.div>

      {isLoading ? (
        <PageSpinner />
      ) : !data?.results.length ? (
        <div className="flex flex-col items-center gap-3 py-24 text-scout-dim">
          <Bell size={56} strokeWidth={1} />
          <p className="text-xl">Уведомлений нет</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {data.results.map((n, i) => (
            <motion.div
              key={n.id}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04 }}
            >
              <Card
                className={`flex items-start gap-4 p-5 transition-colors ${
                  n.is_read ? 'opacity-60' : 'border-scout-accent/30'
                }`}
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-scout-lg bg-scout-success/15">
                  <CheckCircle size={18} className="text-scout-success" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-scout-text">{n.message}</p>
                  <div className="mt-1 flex items-center gap-2">
                    <p className="text-xs text-scout-dim">{formatRelativeDate(n.sent_at)}</p>
                    {n.product_id && n.product_name && (
                      <Link
                        to={`/products/${n.product_id}`}
                        className="text-xs text-scout-accent transition-colors hover:text-scout-accent-hover"
                      >
                        {n.product_name}
                      </Link>
                    )}
                  </div>
                </div>
                {!n.is_read && (
                  <button
                    onClick={() => markRead.mutate(n.id)}
                    className="shrink-0 rounded-scout p-1.5 text-scout-dim transition-colors hover:bg-scout-subtle hover:text-scout-text"
                    title="Отметить прочитанным"
                  >
                    <Check size={16} />
                  </button>
                )}
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </>
  )
}
