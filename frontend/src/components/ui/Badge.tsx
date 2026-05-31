import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

type Variant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'ghost'

const variants: Record<Variant, string> = {
  default: 'bg-scout-accent/15 text-scout-accent',
  success: 'bg-scout-success/15 text-scout-success',
  warning: 'bg-scout-warning/15 text-scout-warning',
  danger:  'bg-scout-danger/15 text-scout-danger',
  info:    'bg-scout-accent/15 text-scout-accent',
  ghost:   'bg-scout-subtle text-scout-muted',
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
        'inline-flex items-center gap-1 rounded-scout px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide',
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}
