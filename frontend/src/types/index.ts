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
  product: number
  source: Source
  url: string
  price: number
  old_price: number | null
  is_available: boolean
  image_url: string | null
  last_seen_at: string
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
