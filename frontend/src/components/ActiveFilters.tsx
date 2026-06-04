import { X } from 'lucide-react'
import { useCatalogFilters } from '@/hooks/useCatalogFilters'

const SOURCE_LABELS: Record<string, string> = {
  dns:      'DNS',
  citilink: 'Ситилинк',
  mvideo:   'М.Видео',
  ozon:     'Ozon',
  wb:       'Wildberries',
}

interface Chip {
  key: string
  label: string
  onRemove: () => void
}

/** Чипы активных опциональных фильтров: показывают всё применённое (включая
 *  скрытые в сайдбаре бренды/цену) и дают снять каждый по отдельности.
 *  Категория не входит — она обязательна и живёт в выпадающем списке. */
export function ActiveFilters() {
  const f = useCatalogFilters()

  if (!f.isAnyActive) return null

  const chips: Chip[] = []

  if (f.search) {
    chips.push({ key: 'search', label: `«${f.search}»`, onRemove: () => f.setFilter('search', '') })
  }
  for (const b of f.brands) {
    chips.push({ key: `brand:${b}`, label: b, onRemove: () => f.toggleArrayValue('brands', b) })
  }
  for (const s of f.sources) {
    chips.push({ key: `source:${s}`, label: SOURCE_LABELS[s] ?? s, onRemove: () => f.toggleArrayValue('sources', s) })
  }
  for (const sp of f.specs) {
    // sp = "cpu_family:core i7" → показываем только значение
    const val = sp.slice(sp.indexOf(':') + 1)
    chips.push({ key: `spec:${sp}`, label: val, onRemove: () => f.toggleArrayValue('specs', sp) })
  }
  if (f.minPrice !== null || f.maxPrice !== null) {
    const lo = f.minPrice !== null ? f.minPrice.toLocaleString('ru-RU') : '0'
    const hi = f.maxPrice !== null ? f.maxPrice.toLocaleString('ru-RU') : '∞'
    chips.push({
      key: 'price',
      label: `${lo}–${hi} ₽`,
      onRemove: () => { f.setFilter('minPrice', null); f.setFilter('maxPrice', null) },
    })
  }
  if (f.inStock) {
    chips.push({ key: 'inStock', label: 'В наличии', onRemove: () => f.setFilter('inStock', false) })
  }

  return (
    <div className="mb-6 flex flex-wrap items-center gap-2">
      {chips.map(c => (
        <button
          key={c.key}
          onClick={c.onRemove}
          className="group flex items-center gap-1.5 rounded-scout border border-scout-subtle bg-scout-elevated px-2.5 py-1 text-xs text-scout-text transition-colors hover:border-scout-accent/60"
        >
          <span>{c.label}</span>
          <X size={12} className="text-scout-dim transition-colors group-hover:text-scout-accent" />
        </button>
      ))}
      <button
        onClick={f.resetAll}
        className="ml-1 text-[10px] uppercase tracking-[0.1em] text-scout-dim transition-colors hover:text-scout-accent"
      >
        Сбросить всё
      </button>
    </div>
  )
}
