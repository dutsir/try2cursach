export type MarketplaceSource = 'wb' | 'ozon' | 'dns' | 'citilink' | 'regard' | string

interface MarketplaceTagProps {
  source: MarketplaceSource
  size?: 'sm' | 'md'
}

const SOURCE_MAP: Record<string, { label: string; full: string }> = {
  wb:       { label: 'WB',  full: 'Wildberries' },
  ozon:     { label: 'OZ',  full: 'Ozon' },
  dns:      { label: 'DNS', full: 'DNS' },
  citilink: { label: 'CL',  full: 'Citilink' },
  regard:   { label: 'RG',  full: 'Regard' },
}

export function MarketplaceTag({ source, size = 'sm' }: MarketplaceTagProps) {
  const m = SOURCE_MAP[source] || { label: source, full: source }

  const padding = size === 'sm' ? 'px-2 py-1' : 'px-2.5 py-1.5'
  const fontSize = size === 'sm' ? 'text-[11px]' : 'text-xs'

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-semibold uppercase tracking-[0.08em] text-scout-muted bg-scout-elevated border border-scout-border rounded-scout ${padding} ${fontSize}`}
    >
      {m.full}
    </span>
  )
}
