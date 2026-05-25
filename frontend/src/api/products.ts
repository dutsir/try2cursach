import { api } from './client'
import type { PaginatedResponse, Product, ProductDetail, PriceHistory, PriceStats } from '@/types'

export interface ProductsParams {
  search?: string
  category?: number | string
  category_slug?: string
  ordering?: string
  page?: number
  page_size?: number
  source?: string
}

export interface Category {
  id: number
  name: string
  slug: string
}

export const productsApi = {
  list: (params?: ProductsParams) =>
    api.get<PaginatedResponse<Product>>('/api/products/', params as Record<string, string | number | boolean | undefined>),

  detail: (id: number) =>
    api.get<ProductDetail>(`/api/products/${id}/`),

  priceHistory: (id: number) =>
    api.get<PriceHistory[]>(`/api/products/${id}/price-history/`),

  priceStats: (id: number) =>
    api.get<PriceStats>(`/api/products/${id}/price-stats/`),

  offers: (id: number) =>
    api.get<{ results: import('@/types').Offer[] }>(`/api/products/${id}/offers/`),
}

export const categoriesApi = {
  list: () =>
    api.get<PaginatedResponse<Category>>('/api/categories/', { page_size: 200, root: true }),
}
