import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Bell, CheckCircle } from 'lucide-react'
import { notificationsApi } from '@/api/subscriptions'
import { Card } from '@/components/ui/Card'
import { PageSpinner } from '@/components/ui/Spinner'
import { formatRelativeDate } from '@/lib/utils'

export default function Notifications() {
  const { data, isLoading } = useQuery({
    queryKey: ['notifications'],
    queryFn: notificationsApi.list,
  })

  return (
    <>
      <motion.div
        className="mb-8 flex items-center gap-3"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Bell size={28} className="text-scout-accent" />
        <div>
          <h1 className="text-3xl font-bold text-scout-text">Уведомления</h1>
          <p className="text-sm text-scout-muted">История оповещений</p>
        </div>
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
              <Card className="flex items-start gap-4 p-5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-scout-lg bg-scout-success/15">
                  <CheckCircle size={18} className="text-scout-success" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-scout-text">{n.message}</p>
                  <p className="mt-1 text-xs text-scout-dim">{formatRelativeDate(n.sent_at)}</p>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </>
  )
}
