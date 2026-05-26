import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * Wrapper над useSearchParams для фильтров каталога.
 * Хранит всё в URL → bookmarking, навигация назад, удобная отладка.
 *
 * Использование:
 *   const f = useCatalogFilters()
 *   f.search        // 'asus'
 *   f.brands        // ['ASUS', 'MSI']
 *   f.setFilter('search', 'rtx 4070')
 *   f.setFilter('brands', ['ASUS', 'MSI'])  // массивы → comma-separated в URL
 *   f.resetAll()
 */
export interface CatalogFilters {
  search: string
  category: string          // category_slug
  brands: string[]          // ['ASUS', 'MSI']
  sources: string[]         // ['dns', 'wb']
  minPrice: number | null
  maxPrice: number | null
  inStock: boolean
  ordering: string          // '', 'name', '-name', 'min_price', '-min_price', '-created_at'
}

const ARRAY_KEYS = ['brands', 'sources'] as const
type ArrayKey = (typeof ARRAY_KEYS)[number]

function isArrayKey(k: string): k is ArrayKey {
  return (ARRAY_KEYS as readonly string[]).includes(k)
}

export function useCatalogFilters() {
  const [params, setParams] = useSearchParams()

  const filters: CatalogFilters = useMemo(() => ({
    search:    params.get('search') || '',
    category:  params.get('category') || '',
    brands:    (params.get('brands') || '').split(',').filter(Boolean),
    sources:   (params.get('sources') || '').split(',').filter(Boolean),
    minPrice:  params.get('min_price') ? Number(params.get('min_price')) : null,
    maxPrice:  params.get('max_price') ? Number(params.get('max_price')) : null,
    inStock:   params.get('in_stock') === 'true',
    ordering:  params.get('ordering') || '',
  }), [params])

  const setFilter = useCallback(<K extends keyof CatalogFilters>(
    key: K, value: CatalogFilters[K],
  ) => {
    setParams(prev => {
      const next = new URLSearchParams(prev)
      const urlKey = key === 'minPrice' ? 'min_price'
                   : key === 'maxPrice' ? 'max_price'
                   : key === 'inStock'  ? 'in_stock'
                   : key
      if (Array.isArray(value)) {
        if (value.length) next.set(urlKey, value.join(','))
        else next.delete(urlKey)
      } else if (typeof value === 'boolean') {
        if (value) next.set(urlKey, 'true')
        else next.delete(urlKey)
      } else if (value === null || value === undefined || value === '') {
        next.delete(urlKey)
      } else {
        next.set(urlKey, String(value))
      }
      return next
    }, { replace: false })
  }, [setParams])

  const toggleArrayValue = useCallback((key: ArrayKey, value: string) => {
    const current = filters[key]
    const next = current.includes(value)
      ? current.filter(v => v !== value)
      : [...current, value]
    setFilter(key, next)
  }, [filters, setFilter])

  const resetAll = useCallback(() => {
    setParams(new URLSearchParams(), { replace: false })
  }, [setParams])

  // Преобразование в формат для productsApi.list()
  const toApiParams = useCallback(() => ({
    ...(filters.search && { search: filters.search }),
    ...(filters.category && { category_slug: filters.category }),
    ...(filters.brands.length && { brand: filters.brands.join(',') }),
    ...(filters.sources.length && { source: filters.sources.join(',') }),
    ...(filters.minPrice !== null && { min_price: filters.minPrice }),
    ...(filters.maxPrice !== null && { max_price: filters.maxPrice }),
    ...(filters.inStock && { in_stock: true }),
    ...(filters.ordering && { ordering: filters.ordering }),
  }), [filters])

  return {
    ...filters,
    setFilter,
    toggleArrayValue,
    resetAll,
    toApiParams,
    isAnyActive: !!(
      filters.search || filters.category || filters.brands.length ||
      filters.sources.length || filters.minPrice !== null ||
      filters.maxPrice !== null || filters.inStock
    ),
  }
}

export { isArrayKey }
