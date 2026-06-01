import { api } from './client'
import type { Product } from '@/types'

export interface BuildItem {
  id: number
  slot: string
  product: Product
  price_snapshot: string
  quantity: number
}

export interface Build {
  id: number
  name: string
  items: BuildItem[]
  total_price: number
  created_at: string
  updated_at: string
}

export const buildsApi = {
  mine: () => api.get<Build>('/api/build/me/'),

  setSlot: (slot: string, productId: number, quantity = 1) =>
    api.post<Build>('/api/build/set-slot/', { slot, product_id: productId, quantity }),

  clearSlot: (slot: string) =>
    api.delete<Build>(`/api/build/clear-slot/${slot}/`),

  clear: () => api.post<Build>('/api/build/clear/', {}),
}
