import { Scout } from './Scout'

interface EmptyDashProps {
  onAddProduct?: () => void
}

const EXAMPLES = [
  { src: 'wb',   label: 'wildberries.ru/catalog/…' },
  { src: 'ozon', label: 'ozon.ru/product/…' },
  { src: 'dns',  label: 'dns-shop.ru/product/…' },
]

export function EmptyDash({ onAddProduct }: EmptyDashProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-32 px-6 min-h-[700px]">
      <Scout size={160} state="sleeping" />

      <div className="mt-8 scout-caption">nothing tracked yet</div>

      <h2 className="mt-4 font-display text-[56px] font-bold tracking-[-0.03em] lowercase text-scout-text">
        add your first product.
      </h2>

      <p className="mt-4 text-base text-scout-muted max-w-[460px] leading-[1.5]">
        paste a link from wildberries, ozon, dns, citilink or regard. scout will start watching within 60 seconds.
      </p>

      <button
        onClick={onAddProduct}
        className="scout-btn-primary mt-10 h-12 px-7 text-sm"
      >
        + добавить товар
      </button>
      <div className="mt-3 text-xs text-scout-dim">либо нажмите ⌘N в любом месте</div>

      <div className="mt-20 flex flex-wrap gap-3 justify-center">
        {EXAMPLES.map(e => (
          <div
            key={e.src}
            className="flex items-center gap-2.5 px-3.5 py-2.5 bg-scout-elevated border border-scout-subtle rounded-scout font-mono text-[11px] text-scout-dim"
          >
            <span className="w-1 h-1 rounded-full bg-scout-accent" />
            {e.label}
          </div>
        ))}
      </div>
    </div>
  )
}
