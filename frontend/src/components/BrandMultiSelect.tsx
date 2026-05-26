import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'

interface BrandOption {
  name: string
  count: number
}

interface Props {
  options: BrandOption[]
  selected: string[]      // выбранные имена (case-insensitive matching на бэке)
  onToggle: (name: string) => void
}

/**
 * Multi-checkbox для брендов с поиском внутри.
 * Показывает топ-20 + поиск по всему списку.
 */
export function BrandMultiSelect({ options, selected, onToggle }: Props) {
  const [q, setQ] = useState('')

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase()
    const list = query
      ? options.filter(o => o.name.toLowerCase().includes(query))
      : options
    return list.slice(0, 20)
  }, [options, q])

  // Selected, которых нет в filtered — показываем сверху
  const selectedSet = useMemo(
    () => new Set(selected.map(s => s.toLowerCase())),
    [selected],
  )
  const extraSelected = selected.filter(
    s => !filtered.some(o => o.name.toLowerCase() === s.toLowerCase()),
  )

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search size={12} className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-steam-muted" />
        <input
          type="text"
          placeholder="Поиск бренда…"
          value={q}
          onChange={e => setQ(e.target.value)}
          className="w-full rounded-steam border border-steam-border bg-steam-darker pl-7 pr-2 py-1.5 text-xs text-steam-light focus:border-steam-blue focus:outline-none"
        />
      </div>

      <div className="max-h-60 overflow-y-auto space-y-1 pr-1">
        {extraSelected.map(name => (
          <label key={`sel-${name}`} className="flex cursor-pointer items-center justify-between gap-2 rounded px-1 py-0.5 hover:bg-steam-darker">
            <span className="flex items-center gap-2 truncate">
              <input
                type="checkbox"
                checked
                onChange={() => onToggle(name)}
                className="h-3.5 w-3.5 accent-steam-blue"
              />
              <span className="text-xs text-steam-light truncate">{name}</span>
            </span>
            <span className="text-[10px] text-steam-muted">✓</span>
          </label>
        ))}
        {filtered.map(opt => {
          const isChecked = selectedSet.has(opt.name.toLowerCase())
          return (
            <label
              key={opt.name}
              className="flex cursor-pointer items-center justify-between gap-2 rounded px-1 py-0.5 hover:bg-steam-darker"
            >
              <span className="flex items-center gap-2 truncate">
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => onToggle(opt.name)}
                  className="h-3.5 w-3.5 accent-steam-blue"
                />
                <span className="text-xs text-steam-light truncate" title={opt.name}>{opt.name}</span>
              </span>
              <span className="text-[10px] text-steam-muted">{opt.count}</span>
            </label>
          )
        })}
        {!filtered.length && (
          <div className="px-1 py-2 text-xs text-steam-muted">Ничего не найдено</div>
        )}
      </div>
    </div>
  )
}
