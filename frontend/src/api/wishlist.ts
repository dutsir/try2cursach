import { api } from './client'
import type { Wishlist } from '@/types'

export const wishlistApi = {
  get: () =>
    api.get<Wishlist>('/api/wishlist/me/'),

  addItem: (productId: number) =>
    api.post('/api/wishlist/add_item/', { product_id: productId, quantity: 1 }),

  removeItem: (itemId: number) =>
    api.delete(`/api/wishlist/remove-item/${itemId}/`),
}
