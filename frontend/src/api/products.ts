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
  brand?: string
  min_price?: number
  max_price?: number
  in_stock?: boolean
}

export interface Category {
  id: number
  name: string
  slug: string
}

export interface CategoryTreeNode {
  id: number
  slug: string
  name: string
  product_count: number
  children: CategoryTreeNode[]
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
}

export const categoriesApi = {
  list: () =>
    api.get<PaginatedResponse<Category>>('/api/categories/', { page_size: 200, root: true }),

  tree: () =>
    api.get<CategoryTreeNode[]>('/api/categories/tree/'),
}
