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
        <div className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-steam-muted">
          {icon}
        </div>
      )}
      <input
        {...props}
        className={cn(
          'w-full rounded-steam border border-steam-border bg-steam-darker px-3 py-2 text-sm text-steam-light placeholder-steam-muted',
          'focus:border-steam-blue focus:outline-none',
          'transition-colors duration-100',
          icon && 'pl-9',
          className,
        )}
      />
    </div>
  )
}
