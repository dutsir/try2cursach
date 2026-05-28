import { cn } from '@/lib/utils'
import type { InputHTMLAttributes, ReactNode } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  icon?: ReactNode
  className?: string
}

export function Input({ icon, className, ...props }: InputProps) {
  return (
    <div className="relative">
      {icon && (
        <div className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-scout-dim">
          {icon}
        </div>
      )}
      <input
        {...props}
        className={cn(
          'w-full rounded-scout border border-scout-subtle bg-scout-elevated px-3 py-2 text-sm text-scout-text placeholder:text-scout-dim',
          'focus:border-scout-accent/60 focus:outline-none',
          'transition-colors duration-150',
          icon && 'pl-9',
          className,
        )}
      />
    </div>
  )
}
