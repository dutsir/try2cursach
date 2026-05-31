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
        'bg-scout-elevated border border-scout-subtle rounded-scout-lg',
        hover && 'cursor-pointer transition-all duration-200 hover:border-scout-border hover:-translate-y-0.5',
        className,
      )}
    >
      {children}
    </div>
  )
}
