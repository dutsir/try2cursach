import { api } from './client'
import type { PaginatedResponse, Product, ProductDetail, PriceHistory } from '@/types'

export interface ProductsParams {
  search?: string
  category?: number
  ordering?: string
  page?: number
  page_size?: number
  source?: string
}

export const productsApi = {
  list: (params?: ProductsParams) =>
    api.get<PaginatedResponse<Product>>('/api/products/', params as Record<string, string | number | boolean | undefined>),

  detail: (id: number) =>
    api.get<ProductDetail>(`/api/products/${id}/`),

  priceHistory: (id: number) =>
    api.get<PriceHistory[]>(`/api/products/${id}/price_history/`),

  offers: (id: number) =>
    api.get<{ results: import('@/types').Offer[] }>(`/api/products/${id}/offers/`),
}
