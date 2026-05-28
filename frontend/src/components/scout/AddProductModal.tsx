import { useState } from 'react'
import { X } from 'lucide-react'
import { ImagePlaceholder } from './ImagePlaceholder'
import { MarketplaceTag } from './MarketplaceTag'

type Stage = 'empty' | 'loading' | 'preview' | 'error'

interface AddProductModalProps {
  onClose: () => void
  onSubmit?: (url: string) => void
}

const SUPPORTED = ['wildberries', 'ozon', 'dns', 'citilink', 'regard']

export function AddProductModal({ onClose, onSubmit }: AddProductModalProps) {
  const [url, setUrl] = useState('')
  const [stage, setStage] = useState<Stage>('empty')

  function handleCheck() {
    if (!url) return
    setStage('loading')
    setTimeout(() => setStage('preview'), 600)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4 animate-fade-in"
      style={{ background: 'rgba(10,10,10,0.7)', backdropFilter: 'blur(8px)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-[600px] bg-scout-elevated border border-scout-border rounded-scout-xl p-8 shadow-[0_24px_80px_rgba(0,0,0,0.6)]"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="scout-caption">new</div>
            <h2 className="mt-1.5 font-display text-[32px] font-bold tracking-[-0.02em] lowercase text-scout-text">
              add product
            </h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-scout text-scout-muted hover:bg-scout-subtle hover:text-scout-text border border-scout-subtle flex items-center justify-center transition-colors"
          >
            <X size={14} />
          </button>
        </div>

        <div className="mt-7">
          <label className="text-[11px] text-scout-muted uppercase tracking-[0.1em]">
            ссылка на товар
          </label>
          <div className="mt-2 flex bg-scout-bg border border-scout-border rounded-scout p-1">
            <input
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="paste a link from wildberries, ozon, dns…"
              className="flex-1 bg-transparent border-none outline-none px-3 py-3 text-sm text-scout-text font-mono placeholder:text-scout-dim"
            />
            <button
              onClick={handleCheck}
              className="px-5 bg-scout-accent hover:bg-scout-accent-hover text-scout-bg text-xs font-semibold rounded-[3px] transition-colors"
            >
              check
            </button>
          </div>
          <div className="mt-2 flex flex-wrap gap-3 items-center text-[11px] text-scout-dim">
            <span>supported:</span>
            {SUPPORTED.map((s, i) => (
              <span key={s} className="text-scout-muted">
                {s}{i < SUPPORTED.length - 1 ? '  ·' : ''}
              </span>
            ))}
          </div>
        </div>

        {stage === 'preview' && (
          <div className="mt-6 p-5 bg-scout-bg rounded-scout-lg" style={{ border: '1px solid rgba(168,85,247,0.3)' }}>
            <div className="flex items-center gap-2 text-[11px] text-scout-success uppercase tracking-[0.1em]">
              <span className="w-1.5 h-1.5 rounded-full bg-scout-success" />
              parsed successfully · 1.2s
            </div>
            <div className="mt-4 flex gap-4">
              <ImagePlaceholder width={88} height={88} label="img" />
              <div className="flex-1">
                <MarketplaceTag source="wb" />
                <div className="mt-2 text-[15px] font-semibold text-scout-text">
                  Предпросмотр товара
                </div>
                <div className="mt-2.5 flex items-baseline gap-2.5">
                  <span className="font-sans text-[22px] font-bold text-scout-accent scout-tabnums">
                    — ₽
                  </span>
                  <span className="text-xs text-scout-dim line-through">— ₽</span>
                </div>
              </div>
            </div>
            <div className="mt-4 text-xs text-scout-muted">
              scout will start watching this product. first datapoint already saved. you'll see history within 4 hours.
            </div>
          </div>
        )}

        {stage === 'loading' && (
          <div className="mt-6 p-5 bg-scout-bg rounded-scout-lg border border-scout-subtle">
            <div className="flex items-center gap-2 text-[11px] text-scout-muted uppercase tracking-[0.1em]">
              <span className="w-1.5 h-1.5 rounded-full bg-scout-accent animate-pulse" />
              parsing…
            </div>
          </div>
        )}

        <div className="mt-8 flex gap-3 justify-end">
          <button onClick={onClose} className="scout-btn-ghost h-10 px-5 text-[13px]">
            cancel
          </button>
          <button
            onClick={() => onSubmit?.(url)}
            disabled={!url}
            className="scout-btn-primary h-10 px-6 text-[13px] disabled:opacity-50 disabled:pointer-events-none"
          >
            add product
          </button>
        </div>
      </div>
    </div>
  )
}
