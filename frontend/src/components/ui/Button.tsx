import { cn } from '@/lib/utils'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Spinner } from './Spinner'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'green'
type Size = 'sm' | 'md' | 'lg' | 'icon'

const base = 'inline-flex items-center justify-center gap-2 font-medium rounded-scout transition-colors duration-150 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed'

const variants: Record<Variant, string> = {
  primary:   'bg-scout-accent text-scout-bg hover:bg-scout-accent-hover font-semibold',
  green:     'bg-scout-success text-scout-bg hover:opacity-90 font-semibold',
  secondary: 'bg-scout-elevated hover:bg-scout-subtle text-scout-text border border-scout-subtle',
  ghost:     'bg-transparent hover:bg-scout-subtle text-scout-muted hover:text-scout-text border border-scout-subtle',
  danger:    'bg-scout-danger/15 hover:bg-scout-danger/25 text-scout-danger border border-scout-danger/30',
}

const sizes: Record<Size, string> = {
  sm:   'px-3 h-8 text-xs',
  md:   'px-4 h-9 text-sm',
  lg:   'px-6 h-11 text-sm',
  icon: 'p-1.5',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  children: ReactNode
}

export function Button({ variant = 'primary', size = 'md', loading, children, className, disabled, ...props }: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={cn(base, variants[variant], sizes[size], className)}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  )
}
