import { Link } from 'react-router-dom'
import { X } from 'lucide-react'
import { useCompareStore, COMPARE_MAX } from '@/store/compare'

/**
 * Floating bar внизу экрана, показывается когда выбран хотя бы 1 товар.
 * Содержит: count, кнопку перехода на /compare и кнопку «Очистить».
 */
export function CompareBar() {
  const ids = useCompareStore(s => s.ids)
  const clear = useCompareStore(s => s.clear)

  if (ids.length === 0) return null

  return (
    <div className="fixed bottom-0 inset-x-0 z-40 border-t border-steam-border bg-steam-darker shadow-[0_-2px_8px_rgba(0,0,0,0.3)]">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold uppercase tracking-wider text-steam-light">
            Сравнение
          </span>
          <span className="text-xs text-steam-muted">
            {ids.length} / {COMPARE_MAX} товаров
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={clear}
            className="flex items-center gap-1 rounded-steam border border-steam-border px-3 py-1.5 text-xs text-steam-muted hover:border-steam-blue hover:text-steam-blue transition-colors"
            title="Очистить сравнение"
          >
            <X size={12} />
            Очистить
          </button>
          <Link
            to={`/compare?ids=${ids.join(',')}`}
            className="rounded-steam bg-steam-blue px-4 py-1.5 text-xs font-bold uppercase tracking-wider text-steam-darker hover:bg-steam-blue/90 transition-colors"
          >
            Сравнить ({ids.length})
          </Link>
        </div>
      </div>
    </div>
  )
}
