import { Link } from 'react-router-dom'
import { X, GitCompare } from 'lucide-react'
import { useCompareStore, COMPARE_MAX } from '@/store/compare'

export function CompareBar() {
  const ids = useCompareStore(s => s.ids)
  const clear = useCompareStore(s => s.clear)

  if (ids.length === 0) return null

  return (
    <div className="fixed bottom-0 inset-x-0 lg:left-[240px] z-40 border-t border-scout-border bg-scout-elevated/95 backdrop-blur-md shadow-[0_-8px_32px_rgba(0,0,0,0.4)]">
      <div className="flex items-center justify-between gap-4 px-6 py-3 max-w-[1440px] mx-auto">
        <div className="flex items-center gap-3">
          <GitCompare size={14} className="text-scout-accent" />
          <span className="text-[12px] uppercase tracking-[0.1em] font-semibold text-scout-text">
            Сравнение
          </span>
          <span className="text-[12px] text-scout-muted scout-tabnums">
            {ids.length} / {COMPARE_MAX} товаров
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={clear}
            className="scout-btn-ghost h-9 text-[12px]"
            title="Очистить сравнение"
          >
            <X size={12} />
            <span className="hidden sm:inline">Очистить</span>
          </button>
          <Link
            to={`/compare?ids=${ids.join(',')}`}
            className="scout-btn-primary h-9 text-[12px]"
          >
            Сравнить ({ids.length})
          </Link>
        </div>
      </div>
    </div>
  )
}
