interface StatTileProps {
  label: string
  value: string | number
  sub?: string
  color?: string
}

function StatTile({ label, value, sub, color = '#F5F5F5' }: StatTileProps) {
  return (
    <div className="bg-scout-elevated border border-scout-subtle rounded-scout-lg p-5">
      <div className="text-[11px] text-scout-dim uppercase tracking-[0.1em]">{label}</div>
      <div
        className="mt-3 font-display text-[32px] font-bold tracking-[-0.02em] scout-tabnums"
        style={{ color }}
      >
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-scout-muted">{sub}</div>}
    </div>
  )
}

interface DashStatsProps {
  tracked: number
  priceRecords?: number
}

export function DashStats({ tracked, priceRecords = 0 }: DashStatsProps) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <StatTile label="Товаров в каталоге" value={tracked.toLocaleString('ru-RU')} sub="всего в базе" />
      <StatTile label="Записей цен" value={priceRecords.toLocaleString('ru-RU')} sub="из всех источников" />
    </div>
  )
}
