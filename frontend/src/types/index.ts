export type Source = 'dns' | 'citilink' | 'ozon'

export interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  avatar: string | null
}

export interface Category {
  id: number
  name: string
  slug: string
  parent: number | null
}

export interface Offer {
  id: number
  product?: number
  source: Source
  source_display?: string
  url: string
  price?: number
  current_price?: string | null
  old_price?: string | null
  is_available?: boolean
  image_url: string | null
  last_seen_at?: string
  vendor_code: string | null
}

export interface Product {
  id: number
  name: string
  slug: string
  category: Category
  brand: string
  vendor_code: string | null
  is_active: boolean
  last_parsed_at: string | null
  best_offer: Offer | null
}

export interface ProductDetail extends Product {
  offers: Offer[]
}

export interface PriceHistory {
  id: number
  price: number
  old_price: number | null
  timestamp: string
  source: Source
  is_actual: boolean
}

export interface PriceStatsWindow {
  min: number | null
  min_date: string | null
  max: number | null
  max_date: string | null
  avg?: number | null
  points?: number
}

export interface PriceStats {
  current: number | null
  history_points: number
  all_time: PriceStatsWindow
  window_30d: PriceStatsWindow
  window_7d: PriceStatsWindow
  delta_7d_pct: number | null
  delta_30d_pct: number | null
  is_min_30d: boolean
  is_min_all_time: boolean
  drop_alert: boolean
  drop_alert_pct: number | null
}

export type PriceWindow = '7d' | '30d' | 'all'

export interface Subscription {
  id: number
  product: Product
  target_price: number
  is_active: boolean
}

export interface Notification {
  id: number
  message: string
  sent_at: string
}

export type AnomalyType = 'spike' | 'manipulation' | 'cyclic'
export type Severity = 'low' | 'medium' | 'high'

export interface Anomaly {
  id: number
  product: Product
  detected_at: string
  anomaly_type: AnomalyType
  severity: Severity
  description: string
  resolved: boolean
}

export interface WishlistItem {
  id: number
  product: Product
  quantity: number
  note: string
  added_at: string
}

export interface Wishlist {
  id: number
  title: string
  description: string
  items: WishlistItem[]
  total_price: number
  created_at: string
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
