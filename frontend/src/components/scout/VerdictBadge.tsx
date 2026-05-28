export type Verdict = 'buy' | 'wait' | 'monitor'

interface VerdictBadgeProps {
  verdict: Verdict
  size?: 'sm' | 'md'
}

const VERDICT_MAP: Record<Verdict, {
  label: string
  color: string
  bg: string
  border: string
}> = {
  buy:     { label: 'Buy Now',  color: '#10B981', bg: 'rgba(16,185,129,0.08)',  border: 'rgba(16,185,129,0.3)' },
  wait:    { label: 'Wait',     color: '#EF4444', bg: 'rgba(239,68,68,0.08)',   border: 'rgba(239,68,68,0.3)' },
  monitor: { label: 'Monitor',  color: '#F59E0B', bg: 'rgba(245,158,11,0.08)',  border: 'rgba(245,158,11,0.3)' },
}

export function VerdictBadge({ verdict, size = 'sm' }: VerdictBadgeProps) {
  const v = VERDICT_MAP[verdict]
  if (!v) return null

  const sizeClasses = size === 'sm' ? 'px-2 py-1 text-[11px]' : 'px-3 py-2 text-[13px]'

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-semibold uppercase tracking-[0.06em] rounded-scout ${sizeClasses}`}
      style={{
        color: v.color,
        background: v.bg,
        border: `1px solid ${v.border}`,
      }}
    >
      <span
        className="rounded-full"
        style={{
          width: 6,
          height: 6,
          background: v.color,
          boxShadow: `0 0 8px ${v.color}`,
        }}
      />
      {v.label}
    </span>
  )
}
