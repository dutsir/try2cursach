import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { facetsApi } from '@/api/facets'
import { useCatalogFilters } from '@/hooks/useCatalogFilters'
import { BrandMultiSelect } from './BrandMultiSelect'
import { PriceRangeSlider } from './PriceRangeSlider'

const SOURCE_LABELS: Record<string, string> = {
  dns:      'DNS',
  citilink: 'Ситилинк',
  ozon:     'Ozon',
  wb:       'Wildberries',
}

/**
 * Sidebar с фильтрами каталога. Подгружает фасеты из API:
 * /api/categories/<slug>/facets/ — но только если выбрана категория.
 * Без категории — показывает только базовые фильтры (источники, наличие).
 */
export function CatalogSidebar() {
  const f = useCatalogFilters()

  // Фасеты — только если категория выбрана
  const { data: facets, isLoading: facetsLoading } = useQuery({
    queryKey: ['facets', f.category],
    queryFn: () => f.category ? facetsApi.forCategory(f.category) : null,
    enabled: !!f.category,
    staleTime: 300_000,
  })

  return (
    <aside className="sticky top-14 h-[calc(100vh-3.5rem)] overflow-y-auto border-r border-steam-border bg-steam-card p-4 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-wider text-steam-light">Фильтры</h3>
        {f.isAnyActive && (
          <button
            onClick={f.resetAll}
            className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-steam-muted hover:text-steam-blue transition-colors"
          >
            <X size={10} />
            Сбросить
          </button>
        )}
      </div>

      {/* Бренды (только при выбранной категории) */}
      {f.category && (
        <section>
          <h4 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-steam-muted">
            Бренды {facets && `(${facets.brands.length})`}
          </h4>
          {facetsLoading ? (
            <div className="text-xs text-steam-muted">Загрузка…</div>
          ) : facets?.brands.length ? (
            <BrandMultiSelect
              options={facets.brands}
              selected={f.brands}
              onToggle={(name) => f.toggleArrayValue('brands', name)}
            />
          ) : (
            <div className="text-xs text-steam-muted">Нет брендов</div>
          )}
        </section>
      )}

      {/* Цена */}
      {f.category && facets?.price_range && facets.price_range.max > facets.price_range.min && (
        <section>
          <h4 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-steam-muted">
            Цена, ₽
          </h4>
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

      {/* Магазин */}
      <section>
        <h4 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-steam-muted">
          Магазин
        </h4>
        <div className="space-y-1">
          {(facets?.sources || [
            { code: 'dns', count: 0 },
            { code: 'wb', count: 0 },
            { code: 'citilink', count: 0 },
            { code: 'ozon', count: 0 },
          ]).map(s => (
            <label
              key={s.code}
              className="flex cursor-pointer items-center justify-between gap-2 rounded px-1 py-0.5 hover:bg-steam-darker"
            >
              <span className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={f.sources.includes(s.code)}
                  onChange={() => f.toggleArrayValue('sources', s.code)}
                  className="h-3.5 w-3.5 accent-steam-blue"
                />
                <span className="text-xs text-steam-light">{SOURCE_LABELS[s.code] || s.code}</span>
              </span>
              {s.count > 0 && (
                <span className="text-[10px] text-steam-muted">{s.count}</span>
              )}
            </label>
          ))}
        </div>
      </section>

      {/* В наличии */}
      <section>
        <label className="flex cursor-pointer items-center justify-between gap-2">
          <span className="text-xs text-steam-light">Только в наличии</span>
          <input
            type="checkbox"
            checked={f.inStock}
            onChange={e => f.setFilter('inStock', e.target.checked)}
            className="h-4 w-4 accent-steam-blue"
          />
        </label>
      </section>

      {facets && (
        <div className="pt-3 border-t border-steam-border text-[10px] text-steam-muted">
          Всего в категории: {facets.total_products.toLocaleString('ru-RU')} товаров
        </div>
      )}
    </aside>
  )
}
