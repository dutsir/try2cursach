import { AlertCircle, RefreshCw } from 'lucide-react'
import { Button } from './Button'

interface QueryErrorProps {
  message?: string | null
  onRetry?: () => void
  className?: string
}

export function QueryError({
  message = 'Не удалось загрузить данные. Проверьте соединение и попробуйте снова.',
  onRetry,
  className = '',
}: QueryErrorProps) {
  return (
    <div className={`flex flex-col items-center gap-4 py-20 px-6 text-center ${className}`}>
      <AlertCircle size={40} className="text-scout-danger" strokeWidth={1.5} />
      <p className="text-sm text-scout-muted max-w-md">{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry} className="gap-2">
          <RefreshCw size={14} />
          Повторить
        </Button>
      )}
    </div>
  )
}
