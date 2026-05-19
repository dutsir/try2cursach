import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

type Variant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'ghost'

const variants: Record<Variant, string> = {
  default: 'bg-steam-blue/15 text-steam-blue',
  success: 'bg-steam-green/15 text-steam-green',
  warning: 'bg-steam-orange/15 text-steam-orange',
  danger:  'bg-red-600/15 text-red-400',
  info:    'bg-steam-blue/15 text-steam-blue',
  ghost:   'bg-steam-border/40 text-steam-light',
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
        'inline-flex items-center gap-1 rounded-steam px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide',
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}
