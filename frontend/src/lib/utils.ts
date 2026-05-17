import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { formatDistanceToNow } from 'date-fns'
import { ru } from 'date-fns/locale/ru'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatPrice(price: number): string {
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(price)
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

export function discount(price: number, oldPrice: number): number {
  return Math.round(((oldPrice - price) / oldPrice) * 100)
}

export const SOURCE_LABELS: Record<string, string> = {
  dns: 'DNS',
  citilink: 'Ситилинк',
  ozon: 'Ozon',
}

export const SOURCE_COLORS: Record<string, string> = {
  dns: '#ef4444',
  citilink: '#f97316',
  ozon: '#3b82f6',
}
