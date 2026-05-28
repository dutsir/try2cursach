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
  avgSavingPct?: number
  parsesPerDay?: number
  anomalies?: number
}

export function DashStats({
  tracked,
  avgSavingPct = 0,
  parsesPerDay = 0,
  anomalies = 0,
}: DashStatsProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      <StatTile label="Отслеживается" value={tracked} sub="товаров" />
      <StatTile
        label="Средняя экономия"
        value={`${avgSavingPct}%`}
        sub="за 30 дней"
        color="#10B981"
      />
      <StatTile
        label="Парсингов / день"
        value={parsesPerDay}
        sub="≈ 1 раз в 4 часа"
      />
      <StatTile
        label="Аномалий найдено"
        value={anomalies}
        sub="за 7 дней"
        color="#F59E0B"
      />
    </div>
  )
}
