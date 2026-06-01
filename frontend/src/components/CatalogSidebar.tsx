import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { facetsApi } from '@/api/facets'
import { useCatalogFilters } from '@/hooks/useCatalogFilters'
import { BrandMultiSelect } from './BrandMultiSelect'
import { PriceRangeSlider } from './PriceRangeSlider'

const SOURCE_LABELS: Record<string, string> = {
  dns:      'DNS',
  citilink: 'Ситилинк',
  mvideo:   'М.Видео',
  ozon:     'Ozon',
  wb:       'Wildberries',
}

export function CatalogSidebar() {
  const f = useCatalogFilters()

  const { data: facets, isLoading: facetsLoading } = useQuery({
    queryKey: ['facets', f.category],
    queryFn: () => f.category ? facetsApi.forCategory(f.category) : null,
    enabled: !!f.category,
    staleTime: 300_000,
  })

  return (
    <aside className="lg:sticky lg:top-16 lg:h-[calc(100vh-4rem)] lg:overflow-y-auto border-b lg:border-b-0 lg:border-r border-scout-subtle bg-scout-bg p-5 space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="scout-caption text-scout-text">Фильтры</h3>
        {f.isAnyActive && (
          <button
            onClick={f.resetAll}
            className="flex items-center gap-1 text-[10px] uppercase tracking-[0.1em] text-scout-dim hover:text-scout-accent transition-colors"
          >
            <X size={10} />
            Сбросить
          </button>
        )}
      </div>

      {f.category && (
        <section>
          <h4 className="mb-2.5 scout-caption">
            Бренды {facets && `(${facets.brands.length})`}
          </h4>
          {facetsLoading ? (
            <div className="text-xs text-scout-dim">Загрузка…</div>
          ) : facets?.brands.length ? (
            <BrandMultiSelect
              options={facets.brands}
              selected={f.brands}
              onToggle={(name) => f.toggleArrayValue('brands', name)}
            />
          ) : (
            <div className="text-xs text-scout-dim">Нет брендов</div>
          )}
        </section>
      )}

      {f.category && facets?.price_range && facets.price_range.max > facets.price_range.min && (
        <section>
          <h4 className="mb-2.5 scout-caption">Цена, ₽</h4>
          <PriceRangeSlider
            min={facets.price_range.min}
            max={facets.price_range.max}
            value={[f.minPrice, f.maxPrice]}
            onChange={([lo, hi]) => {
              f.setFilter('minPrice', lo)
              f.setFilter('maxPrice', hi)
            }}
          />
        </section>
      )}

      <section>
        <h4 className="mb-2.5 scout-caption">Магазин</h4>
        <div className="space-y-1">
          {(facets?.sources || [
            { code: 'dns', count: 0 },
            { code: 'citilink', count: 0 },
            { code: 'mvideo', count: 0 },
            { code: 'wb', count: 0 },
            { code: 'ozon', count: 0 },
          ]).map(s => (
            <label
              key={s.code}
              className="flex cursor-pointer items-center justify-between gap-2 rounded-scout px-2 py-1.5 hover:bg-scout-subtle/60 transition-colors"
            >
              <span className="flex items-center gap-2.5">
                <input
                  type="checkbox"
                  checked={f.sources.includes(s.code)}
                  onChange={() => f.toggleArrayValue('sources', s.code)}
                  className="h-3.5 w-3.5 accent-scout-accent"
                />
                <span className="text-xs text-scout-text">{SOURCE_LABELS[s.code] || s.code}</span>
              </span>
              {s.count > 0 && (
                <span className="text-[10px] text-scout-dim scout-tabnums">{s.count}</span>
              )}
            </label>
          ))}
        </div>
      </section>

      <section>
        <label className="flex cursor-pointer items-center justify-between gap-2 rounded-scout px-2 py-1.5 hover:bg-scout-subtle/60 transition-colors">
          <span className="text-xs text-scout-text">Только в наличии</span>
          <input
            type="checkbox"
            checked={f.inStock}
            onChange={e => f.setFilter('inStock', e.target.checked)}
            className="h-4 w-4 accent-scout-accent"
          />
        </label>
      </section>

      {facets && (
        <div className="pt-4 border-t border-scout-subtle text-[10px] text-scout-dim">
          Всего в категории: <span className="scout-tabnums text-scout-muted">{facets.total_products.toLocaleString('ru-RU')}</span> товаров
        </div>
      )}
    </aside>
  )
}
