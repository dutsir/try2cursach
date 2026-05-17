import { cn } from '@/lib/utils'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Spinner } from './Spinner'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg' | 'icon'

const base = 'inline-flex items-center justify-center gap-2 font-medium rounded-xl transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50 disabled:cursor-not-allowed'

const variants: Record<Variant, string> = {
  primary:   'bg-brand-600 hover:bg-brand-500 active:scale-95 text-white shadow-lg shadow-brand-900/40',
  secondary: 'bg-white/10 hover:bg-white/20 active:scale-95 text-white border border-white/20',
  ghost:     'hover:bg-white/10 active:scale-95 text-white/70 hover:text-white',
  danger:    'bg-red-600 hover:bg-red-500 active:scale-95 text-white',
}

const sizes: Record<Size, string> = {
  sm:   'px-3 py-1.5 text-sm',
  md:   'px-4 py-2 text-sm',
  lg:   'px-6 py-3 text-base',
  icon: 'p-2',
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
