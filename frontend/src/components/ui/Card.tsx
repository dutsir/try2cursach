import { cn } from '@/lib/utils'
import type { HTMLAttributes } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hover?: boolean
}

export function Card({ hover, className, children, ...props }: CardProps) {
  return (
    <div
      {...props}
      className={cn(
        'rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl',
        'shadow-xl shadow-black/20',
        hover && 'cursor-pointer transition-all duration-300 hover:scale-[1.02] hover:border-white/20 hover:bg-white/10 hover:shadow-2xl',
        className,
      )}
    >
      {children}
    </div>
  )
}
