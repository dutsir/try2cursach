import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { formatDistanceToNow } from 'date-fns'
import { ru } from 'date-fns/locale/ru'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatPrice(price: number | string | null | undefined): string {
  if (!price) return '—'
  const num = typeof price === 'string' ? parseFloat(price) : price
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(num)
}

export function formatRelativeDate(dateStr: string): string {
  try {
    return formatDistanceToNow(new Date(dateStr), { addSuffix: true, locale: ru })
  } catch {
    return dateStr
  }
}

export function formatDate(dateStr: string): string {
  try {
    return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(dateStr))
  } catch {
    return dateStr
  }
}

export function discount(price?: number | string | null, oldPrice?: number | string | null): number {
  if (!price || !oldPrice) return 0
  const p = typeof price === 'string' ? parseFloat(price) : price
  const op = typeof oldPrice === 'string' ? parseFloat(oldPrice) : oldPrice
  if (!p || !op) return 0
  return Math.round(((op - p) / op) * 100)
}

export const SOURCE_LABELS: Record<string, string> = {
  dns: 'DNS',
  citilink: 'Ситилинк',
  ozon: 'Ozon',
  wb: 'Wildberries',
  regard: 'Regard',
  mvideo: 'М.Видео',
}

export const SOURCE_COLORS: Record<string, string> = {
  dns: '#ef4444',
  citilink: '#f97316',
  ozon: '#3b82f6',
  wb: '#a855f7',
  regard: '#22c55e',
  mvideo: '#e11d48',
}
