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
        'bg-steam-card border border-steam-border rounded-steam',
        hover && 'cursor-pointer transition-colors duration-100 hover:border-steam-blue/60 hover:bg-steam-panel',
        className,
      )}
    >
      {children}
    </div>
  )
}
