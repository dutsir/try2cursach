import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { formatDistanceToNow } from 'date-fns'
import { ru } from 'date-fns/locale/ru'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Оффер из списка (price) или карточки (current_price). */
export type PriceLike = {
  price?: number | string | null
  current_price?: number | string | null
  old_price?: number | string | null
} | null | undefined

export function parsePriceValue(value: number | string | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (!Number.isFinite(num) || num <= 0) return null
  return num
}

export function getOfferPrice(offer: PriceLike): number | null {
  if (!offer) return null
  return parsePriceValue(offer.price) ?? parsePriceValue(offer.current_price)
}

export function getOfferOldPrice(offer: PriceLike): number | null {
  if (!offer) return null
  return parsePriceValue(offer.old_price)
}

export function formatPrice(price: number | string | null | undefined): string {
  const num = parsePriceValue(price)
  if (num === null) return '—'
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
  const p = parsePriceValue(price)
  const op = parsePriceValue(oldPrice)
  if (p === null || op === null || op <= p) return 0
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
