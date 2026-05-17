import { api } from './client'
import type { PaginatedResponse, Subscription, Notification } from '@/types'

export const subscriptionsApi = {
  list: () =>
    api.get<PaginatedResponse<Subscription>>('/api/subscriptions/'),

  create: (productId: number, targetPrice: number) =>
    api.post<Subscription>('/api/subscriptions/', { product: productId, target_price: targetPrice }),

  delete: (id: number) =>
    api.delete(`/api/subscriptions/${id}/`),

  update: (id: number, data: Partial<Pick<Subscription, 'target_price' | 'is_active'>>) =>
    api.patch<Subscription>(`/api/subscriptions/${id}/`, data),
}

export const notificationsApi = {
  list: () =>
    api.get<PaginatedResponse<Notification>>('/api/notifications/'),
}
