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
        <div className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-white/40">
          {icon}
        </div>
      )}
      <input
        {...props}
        className={cn(
          'w-full rounded-xl border border-white/15 bg-white/10 px-4 py-2.5 text-white placeholder-white/40',
          'focus:border-brand-500/50 focus:outline-none focus:ring-2 focus:ring-brand-500/30',
          'transition-all duration-200',
          icon && 'pl-10',
          className,
        )}
      />
    </div>
  )
}
