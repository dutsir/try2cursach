import { api } from './client'
import type { User } from '@/types'

export interface TelegramLinkInfo {
  code: string
  bot_username: string
  deep_link: string | null
  instructions: string
  expires_in_minutes: number
}

export interface TelegramStatus {
  linked: boolean
  telegram_username: string
  notify_telegram: boolean
}

export const accountApi = {
  me: () => api.get<User>('/api/auth/me/'),

  updateProfile: (data: Partial<Pick<User, 'first_name' | 'last_name' | 'notify_telegram'>>) =>
    api.patch<User>('/api/auth/me/', data),

  telegramStatus: () => api.get<TelegramStatus>('/api/telegram/status/'),

  telegramLink: () => api.post<TelegramLinkInfo>('/api/telegram/link/', {}),

  telegramUnlink: () => api.post<{ linked: boolean }>('/api/telegram/unlink/', {}),
}
