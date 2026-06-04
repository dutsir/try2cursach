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

  updateProfile: (data: Partial<Pick<User, 'first_name' | 'last_name' | 'notify_telegram' | 'notify_email'>>) =>
    api.patch<User>('/api/auth/me/', data),

  telegramStatus: () => api.get<TelegramStatus>('/api/telegram/status/'),

  telegramLink: () => api.post<TelegramLinkInfo>('/api/telegram/link/', {}),

  telegramUnlink: () => api.post<{ linked: boolean }>('/api/telegram/unlink/', {}),

  verifyEmail: (token: string) =>
    api.post<{ ok: boolean; message: string }>('/api/auth/verify-email/', { token }),

  resendVerification: () =>
    api.post<{ ok: boolean; message: string }>('/api/auth/resend-verification/', {}),

  requestPasswordReset: (email: string) =>
    api.post<{ ok: boolean; message: string }>('/api/auth/password-reset/', { email }),

  confirmPasswordReset: (uid: string, token: string, password: string, password_confirm: string) =>
    api.post<{ ok: boolean; message: string }>('/api/auth/password-reset-confirm/', {
      uid, token, password, password_confirm,
    }),

  changePassword: (current_password: string, new_password: string, new_password_confirm: string) =>
    api.post<{ ok: boolean; message: string }>('/api/auth/change-password/', {
      current_password, new_password, new_password_confirm,
    }),

  changeEmail: (email: string, password: string) =>
    api.post<User>('/api/auth/change-email/', { email, password }),
}
