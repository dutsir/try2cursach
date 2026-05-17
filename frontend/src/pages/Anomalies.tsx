import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { TrendingUp, AlertTriangle, RefreshCw } from 'lucide-react'
import { api } from '@/api/client'
import type { PaginatedResponse, Anomaly } from '@/types'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { PageSpinner } from '@/components/ui/Spinner'
import { formatRelativeDate, formatPrice } from '@/lib/utils'

const SEVERITY_VARIANT = { low: 'info', medium: 'warning', high: 'danger' } as const
const SEVERITY_LABEL = { low: 'Низкая', medium: 'Средняя', high: 'Высокая' } as const
const TYPE_LABEL: Record<string, string> = {
  spike: 'Скачок цены',
  manipulation: 'Манипуляция',
  cyclic: 'Цикличное изменение',
}
const TYPE_ICON: Record<string, typeof TrendingUp> = {
  spike: TrendingUp,
  manipulation: AlertTriangle,
  cyclic: RefreshCw,
}

export default function Anomalies() {
  const { data, isLoading } = useQuery({
    queryKey: ['anomalies'],
    queryFn: () => api.get<PaginatedResponse<Anomaly>>('/api/anomalies/'),
  })

  return (
    <>
      <motion.div
        className="mb-8 flex items-center gap-3"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <TrendingUp size={28} className="text-brand-400" />
        <div>
          <h1 className="text-3xl font-bold text-white">Аномалии цен</h1>
          <p className="text-sm text-white/50">Подозрительные изменения цен</p>
        </div>
      </motion.div>

      {isLoading ? (
        <PageSpinner />
      ) : !data?.results.length ? (
        <div className="flex flex-col items-center gap-3 py-24 text-white/40">
          <TrendingUp size={56} strokeWidth={1} />
          <p className="text-xl">Аномалий не обнаружено</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {data.results.map((anomaly, i) => {
            const Icon = TYPE_ICON[anomaly.anomaly_type] ?? AlertTriangle
            return (
              <motion.div
                key={anomaly.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <Card className="flex items-start gap-5 p-5">
                  <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
                    anomaly.severity === 'high'   ? 'bg-red-600/20' :
                    anomaly.severity === 'medium' ? 'bg-amber-600/20' :
                                                    'bg-sky-600/20'
                  }`}>
                    <Icon size={20} className={
                      anomaly.severity === 'high'   ? 'text-red-400' :
                      anomaly.severity === 'medium' ? 'text-amber-400' :
                                                      'text-sky-400'
                    } />
                  </div>

                  <div className="flex flex-1 flex-col gap-2 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={`/products/${anomaly.product.id}`}
                        className="font-semibold text-white hover:text-brand-300 transition truncate"
                      >
                        {anomaly.product.name}
                      </Link>
                    </div>

                    <p className="text-sm text-white/60">{anomaly.description}</p>

                    <div className="flex flex-wrap gap-2">
                      <Badge variant={SEVERITY_VARIANT[anomaly.severity]}>
                        {SEVERITY_LABEL[anomaly.severity]}
                      </Badge>
                      <Badge variant="ghost">
                        {TYPE_LABEL[anomaly.anomaly_type] ?? anomaly.anomaly_type}
                      </Badge>
                      {anomaly.resolved && (
                        <Badge variant="success">Решено</Badge>
                      )}
                    </div>

                    <p className="text-xs text-white/30">{formatRelativeDate(anomaly.detected_at)}</p>
                  </div>
                </Card>
              </motion.div>
            )
          })}
        </div>
      )}
    </>
  )
}
