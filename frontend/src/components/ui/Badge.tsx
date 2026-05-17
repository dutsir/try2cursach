import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

type Variant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'ghost'

const variants: Record<Variant, string> = {
  default: 'bg-brand-500/20 text-brand-300 border-brand-500/30',
  success: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  warning: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  danger:  'bg-red-500/20 text-red-400 border-red-500/30',
  info:    'bg-sky-500/20 text-sky-400 border-sky-500/30',
  ghost:   'bg-white/10 text-white/70 border-white/20',
}

interface BadgeProps {
  variant?: Variant
  children: ReactNode
  className?: string
}

export function Badge({ variant = 'default', children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}
