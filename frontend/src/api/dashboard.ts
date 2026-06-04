import { api } from './client'

export interface DashboardDeal {
  id: number
  name: string
  slug: string
  brand: string
  category_name: string
  image_url: string
  price: string
  old_price: string
  discount_pct: number
  is_min_30d?: boolean
  is_price_min?: boolean
  source: string
  source_display: string
  url: string
}

export interface DashboardCategory {
  id: number
  slug: string
  name: string
  count: number
}

export interface DashboardResponse {
  totals: {
    products: number
    categories: number
    offers: number
    price_records: number
    price_records_24h: number
  }
  top_deals: DashboardDeal[]
  popular_categories: DashboardCategory[]
}

export const dashboardApi = {
  get: () => api.get<DashboardResponse>('/api/dashboard/'),
}
