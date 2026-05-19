import { cn } from '@/lib/utils'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Spinner } from './Spinner'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'green'
type Size = 'sm' | 'md' | 'lg' | 'icon'

const base = 'inline-flex items-center justify-center gap-2 font-medium rounded-steam transition-colors duration-100 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed'

const variants: Record<Variant, string> = {
  primary:   'steam-btn-primary',
  green:     'steam-btn-green',
  secondary: 'bg-steam-panel hover:bg-steam-border text-steam-light border border-steam-border',
  ghost:     'bg-steam-blue/10 hover:bg-steam-blue/20 text-steam-light hover:text-white',
  danger:    'bg-[#5a1a1a] hover:bg-[#7a2222] text-white',
}

const sizes: Record<Size, string> = {
  sm:   'px-3 py-1 text-xs',
  md:   'px-4 py-1.5 text-sm',
  lg:   'px-6 py-2 text-sm',
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
