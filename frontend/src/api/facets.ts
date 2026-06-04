import { api } from './client'

export interface SpecFacet {
  key: string
  label: string
  values: { value: string; count: number }[]
}

export interface CategoryFacets {
  category: { id: number; slug: string; name: string }
  brands: { name: string; count: number }[]
  price_range: { min: number; max: number }
  sources: { code: string; count: number }[]
  specs: SpecFacet[]
  total_products: number
}

export const facetsApi = {
  forCategory: (slug: string) =>
    api.get<CategoryFacets>(`/api/categories/${slug}/facets/`),
}
