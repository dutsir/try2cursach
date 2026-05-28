import { api } from './client'

export interface OfferBySource {
  price: string
  old_price: string | null
  source_display: string
  url: string
  image_url: string
  is_available: boolean
  rating: number | null
  reviews_count: number | null
}

export interface CompareItem {
  id: number
  name: string
  slug: string
  brand: string
  category: { id: number; slug: string; name: string } | null
  image_url: string
  best_offer: {
    price: string
    old_price: string | null
    source: string
    source_display: string
    url: string
    image_url: string
  } | null
  offers_by_source: Record<string, OfferBySource>
  price_trend: {
    price_30d_ago: string
    delta: string
    delta_pct: number
  } | null
  stats: {
    rating: number | null
    reviews_count: number | null
    sale_percent: number | null
    cashback_percent: number | null
    supplier: string | null
    supplier_rating: number | null
  }
  specs: Record<string, unknown>
  offers_count: number
  value_score: number
}

export interface AISummaryResponse {
  verdict: string
  cached: boolean
}

export const compareApi = {
  get: (ids: number[]) =>
    api.get<CompareItem[]>('/api/compare/', { ids: ids.join(',') }),
  aiSummary: (ids: number[]) =>
    api.get<AISummaryResponse>('/api/compare/ai-summary/', { ids: ids.join(',') }),
}
