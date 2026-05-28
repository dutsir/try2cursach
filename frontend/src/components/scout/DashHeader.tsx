import { LayoutGrid, List } from 'lucide-react'

export type DashFilter = 'all' | 'buy' | 'wait' | 'monitor'
export type DashView = 'grid' | 'list'

interface DashHeaderProps {
  filter: DashFilter
  setFilter: (f: DashFilter) => void
  view: DashView
  setView: (v: DashView) => void
  greeting?: string
  subtitle?: string
  dateLine?: string
  counts: Record<DashFilter, number>
}

const TABS: { key: DashFilter; label: string; dotColor?: string }[] = [
  { key: 'all',     label: 'Все' },
  { key: 'buy',     label: 'Можно купить', dotColor: '#10B981' },
  { key: 'wait',    label: 'Подождать',    dotColor: '#EF4444' },
  { key: 'monitor', label: 'Мониторим',    dotColor: '#F59E0B' },
]

export function DashHeader({
  filter,
  setFilter,
  view,
  setView,
  greeting = 'добрый день.',
  subtitle = 'статус загрузки.',
  dateLine,
  counts,
}: DashHeaderProps) {
  const today = dateLine ?? formatToday()

  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
      <div>
        <div className="scout-caption">{today}</div>
        <h1 className="mt-2 font-display text-[40px] font-bold tracking-[-0.02em] lowercase text-scout-text">
          {greeting}
        </h1>
        <p className="mt-2 text-sm text-scout-muted">{subtitle}</p>
      </div>

      <div className="flex items-center gap-2">
        <div className="flex gap-0.5 bg-scout-elevated p-0.5 rounded-scout border border-scout-subtle">
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setFilter(t.key)}
              className={`px-3 py-2 rounded-[3px] text-xs font-medium flex gap-1.5 items-center transition-colors ${
                filter === t.key
                  ? 'bg-scout-subtle text-scout-text'
                  : 'bg-transparent text-scout-muted hover:text-scout-text'
              }`}
            >
              {t.dotColor && (
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: t.dotColor }} />
              )}
              {t.label}
              <span className="text-scout-dim scout-tabnums">{counts[t.key]}</span>
            </button>
          ))}
        </div>

        <div className="flex gap-0.5 bg-scout-elevated p-0.5 rounded-scout border border-scout-subtle">
          <button
            onClick={() => setView('grid')}
            className={`w-[30px] h-[30px] rounded-[3px] flex items-center justify-center transition-colors ${
              view === 'grid' ? 'bg-scout-subtle text-scout-text' : 'text-scout-muted hover:text-scout-text'
            }`}
            title="Сетка"
          >
            <LayoutGrid size={14} />
          </button>
          <button
            onClick={() => setView('list')}
            className={`w-[30px] h-[30px] rounded-[3px] flex items-center justify-center transition-colors ${
              view === 'list' ? 'bg-scout-subtle text-scout-text' : 'text-scout-muted hover:text-scout-text'
            }`}
            title="Список"
          >
            <List size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}

function formatToday(): string {
  const d = new Date()
  const days = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота']
  const months = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
  ]
  const day = days[d.getDay()]
  const date = d.getDate()
  const month = months[d.getMonth()]
  const hours = d.getHours().toString().padStart(2, '0')
  const minutes = d.getMinutes().toString().padStart(2, '0')
  return `${day} · ${date} ${month}, ${hours}:${minutes}`
}
