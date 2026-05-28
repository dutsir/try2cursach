import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  X, Package, ExternalLink, ArrowLeft,
  TrendingDown, TrendingUp, Star, Sparkles, AlertCircle,
} from 'lucide-react'
import { compareApi } from '@/api/compare'
import { useCompareStore } from '@/store/compare'
import { formatPrice, cn } from '@/lib/utils'
import { Spinner } from '@/components/ui/Spinner'

export default function Compare() {
  const [searchParams] = useSearchParams()
  const idsParam = searchParams.get('ids') || ''
  const ids = useMemo(
    () => idsParam.split(',').map(Number).filter(n => !isNaN(n) && n > 0),
    [idsParam],
  )

  const remove = useCompareStore(s => s.remove)
  const [aiVerdict, setAiVerdict] = useState<string | null>(null)
  const [aiCached, setAiCached] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['compare', ids],
    queryFn: () => compareApi.get(ids),
    enabled: ids.length > 0,
  })

  const aiMutation = useMutation({
    mutationFn: () => compareApi.aiSummary(ids),
    onSuccess: (res) => {
      setAiVerdict(res.verdict)
      setAiCached(res.cached)
      setAiError(null)
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.error || err?.message || 'Не удалось получить вердикт'
      setAiError(msg)
      setAiVerdict(null)
    },
  })

  if (!ids.length) {
    return (
      <div className="py-20 text-center animate-scout-rise">
        <div className="scout-caption mb-3">compare</div>
        <h2 className="font-display text-[40px] font-bold tracking-[-0.02em] lowercase text-scout-text mb-3">
          nothing to compare yet.
        </h2>
        <p className="text-sm text-scout-muted mb-6">
          выбери товары в каталоге, чтобы сравнить их рядом.
        </p>
        <Link to="/catalog" className="scout-btn-primary inline-flex">
          <ArrowLeft size={14} />
          в каталог
        </Link>
      </div>
    )
  }

  if (isLoading) {
    return <div className="flex justify-center py-20"><Spinner /></div>
  }

  const items = data || []
  if (!items.length) {
    return (
      <div className="py-20 text-center text-scout-muted animate-scout-rise">
        <p>Товары не найдены</p>
      </div>
    )
  }

  const allSpecKeys = Array.from(new Set(items.flatMap(i => Object.keys(i.specs || {}))))
    .filter(k => !['tokens', 'category_id', 'source_sku', 'model_code_source', 'clean_name', 'source'].includes(k))
    .sort()

  const maxValueScore = Math.max(...items.map(i => i.value_score || 0))
  const prices = items.map(i => Number(i.best_offer?.price || Infinity))
  const minPrice = Math.min(...prices.filter(p => isFinite(p)))
  const ratings = items.map(i => Number(i.stats?.rating || 0))
  const maxRating = Math.max(...ratings, 0)

  const hasRatings   = items.some(i => i.stats?.rating)
  const hasReviews   = items.some(i => i.stats?.reviews_count)
  const hasSuppliers = items.some(i => i.stats?.supplier)
  const hasSales     = items.some(i => i.stats?.sale_percent)
  const hasCashback  = items.some(i => i.stats?.cashback_percent)
  const hasOffers    = items.some(i => Object.keys(i.offers_by_source || {}).length > 0)

  return (
    <div className="animate-scout-rise space-y-6">
      {/* Breadcrumb + heading */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link
            to="/catalog"
            className="inline-flex items-center gap-1 text-[11px] uppercase tracking-[0.12em] text-scout-dim hover:text-scout-accent transition-colors"
          >
            <ArrowLeft size={11} /> к каталогу
          </Link>
          <h1 className="mt-3 font-display text-[40px] font-bold tracking-[-0.02em] lowercase text-scout-text">
            сравнение товаров
          </h1>
          <p className="mt-1 text-sm text-scout-muted">
            {items.length} {pluralItems(items.length)} рядом · подсветка лучшего значения по каждому критерию
          </p>
        </div>
      </div>

      {/* AI verdict */}
      <div className="rounded-scout-lg border p-5"
           style={{ borderColor: 'rgba(168,85,247,0.3)', background: 'linear-gradient(180deg, #141414 0%, #0F0A1A 100%)' }}>
        {!aiVerdict && !aiError && (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Sparkles size={16} className="text-scout-accent" />
              <div>
                <div className="text-[13px] font-semibold text-scout-text">AI-сравнение товаров</div>
                <div className="text-[11px] text-scout-muted">3-5 предложений с рекомендацией</div>
              </div>
            </div>
            <button
              onClick={() => aiMutation.mutate()}
              disabled={aiMutation.isPending || items.length < 2}
              className="scout-btn-primary disabled:opacity-50 disabled:pointer-events-none"
            >
              {aiMutation.isPending ? (
                <>
                  <Spinner /> Анализирую…
                </>
              ) : (
                <>
                  <Sparkles size={12} /> сгенерировать
                </>
              )}
            </button>
          </div>
        )}

        {aiVerdict && (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-scout-accent" />
                <span className="text-[13px] font-semibold text-scout-text">Вердикт AI</span>
                {aiCached && (
                  <span className="text-[10px] uppercase tracking-[0.1em] text-scout-dim bg-scout-bg border border-scout-subtle px-2 py-0.5 rounded-[3px]">
                    из кэша
                  </span>
                )}
              </div>
              <button
                onClick={() => { setAiVerdict(null); setAiCached(false) }}
                className="text-[11px] uppercase tracking-[0.1em] text-scout-dim hover:text-scout-text transition-colors"
              >
                Скрыть
              </button>
            </div>
            <p className="text-sm text-scout-text leading-relaxed whitespace-pre-line">
              {aiVerdict}
            </p>
            <div className="text-[10px] text-scout-dim pt-2 border-t border-scout-subtle">
              Сгенерировано Gemini AI — рекомендация модели, не окончательный совет
            </div>
          </div>
        )}

        {aiError && (
          <div className="flex items-start gap-3">
            <AlertCircle size={16} className="text-scout-danger flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="text-[13px] font-semibold text-scout-danger mb-1">
                Не удалось сгенерировать вердикт
              </div>
              <div className="text-xs text-scout-muted">{aiError}</div>
              <button
                onClick={() => { setAiError(null); aiMutation.mutate() }}
                className="mt-2 text-[11px] uppercase tracking-[0.1em] text-scout-accent hover:text-scout-accent-hover transition-colors"
              >
                Попробовать снова
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Comparison table */}
      <div className="overflow-x-auto rounded-scout-lg border border-scout-subtle bg-scout-elevated">
        <table className="w-full border-collapse" style={{ minWidth: `${200 + items.length * 224}px` }}>
          <thead>
            <tr className="bg-scout-bg">
              <th className="sticky left-0 z-10 w-48 bg-scout-bg border-r border-scout-subtle p-2 align-top" />
              {items.map(item => (
                <th key={item.id} className="w-56 border-r border-scout-subtle p-3 align-top">
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <Link to={`/products/${item.id}`} className="block flex-1 min-w-0">
                      {item.image_url || item.best_offer?.image_url ? (
                        <img
                          src={item.image_url || item.best_offer?.image_url || ''}
                          alt={item.name}
                          className="h-24 w-full object-contain bg-scout-bg rounded-scout p-1"
                        />
                      ) : (
                        <div className="flex h-24 w-full items-center justify-center bg-scout-bg rounded-scout border border-scout-subtle">
                          <Package size={32} className="text-scout-dim" />
                        </div>
                      )}
                    </Link>
                    <button
                      onClick={() => remove(item.id)}
                      className="p-1 text-scout-dim hover:text-scout-danger flex-shrink-0 transition-colors"
                      title="Убрать из сравнения"
                    >
                      <X size={14} />
                    </button>
                  </div>
                  <Link
                    to={`/products/${item.id}`}
                    className="text-[12px] font-medium text-scout-text line-clamp-3 hover:text-scout-accent block mb-1 text-left transition-colors"
                  >
                    {item.name}
                  </Link>
                  {item.brand && (
                    <div className="text-[10px] uppercase tracking-[0.08em] text-scout-dim text-left">
                      {item.brand}
                    </div>
                  )}

                  {/* Value Score */}
                  <div className="mt-3 p-2 bg-scout-bg rounded-scout border border-scout-subtle">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] uppercase tracking-[0.1em] text-scout-dim">Value</span>
                      <span className={cn(
                        'text-xs font-bold scout-tabnums',
                        item.value_score === maxValueScore && item.value_score > 0
                          ? 'text-scout-success'
                          : 'text-scout-text',
                      )}>
                        {item.value_score}%
                      </span>
                    </div>
                    <div className="w-full bg-scout-subtle rounded-full h-1 overflow-hidden">
                      <div
                        className="bg-scout-success h-1 rounded-full transition-all"
                        style={{ width: `${item.value_score}%` }}
                      />
                    </div>
                  </div>
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {/* ============ ЦЕНА ============ */}
            <GroupHeader title="Цена" colSpan={items.length + 1} />
            <Row label="Текущая цена">
              {items.map(item => {
                const price = Number(item.best_offer?.price || 0)
                const isBest = price === minPrice && price > 0
                return (
                  <Cell key={item.id} highlight={isBest}>
                    {price > 0 ? (
                      <div>
                        <div className="text-base font-bold text-scout-accent scout-tabnums">
                          {formatPrice(price)}
                        </div>
                        {item.best_offer?.old_price && (
                          <div className="text-[10px] text-scout-dim line-through scout-tabnums">
                            {formatPrice(Number(item.best_offer.old_price))}
                          </div>
                        )}
                        <div className="text-[10px] text-scout-muted mt-1">
                          {item.best_offer?.source_display}
                        </div>
                        {isBest && (
                          <div className="mt-1 inline-block text-[9px] uppercase tracking-[0.1em] text-scout-success bg-scout-success/10 px-1.5 py-0.5 rounded-[3px]">
                            лучшая
                          </div>
                        )}
                      </div>
                    ) : <Dash />}
                  </Cell>
                )
              })}
            </Row>

            <Row label="Динамика (30д)">
              {items.map(item => (
                <Cell key={item.id}>
                  {item.price_trend ? (
                    <div className="flex items-center gap-2">
                      {item.price_trend.delta_pct < 0 ? (
                        <TrendingDown size={14} className="text-scout-success flex-shrink-0" />
                      ) : (
                        <TrendingUp size={14} className="text-scout-danger flex-shrink-0" />
                      )}
                      <div>
                        <div className={cn(
                          'text-xs font-bold scout-tabnums',
                          item.price_trend.delta_pct < 0 ? 'text-scout-success' : 'text-scout-danger',
                        )}>
                          {item.price_trend.delta_pct > 0 ? '+' : ''}{item.price_trend.delta_pct}%
                        </div>
                        <div className="text-[10px] text-scout-dim scout-tabnums">
                          было {formatPrice(Number(item.price_trend.price_30d_ago))}
                        </div>
                      </div>
                    </div>
                  ) : <span className="text-scout-dim text-xs">нет данных</span>}
                </Cell>
              ))}
            </Row>

            {/* ============ КАЧЕСТВО ============ */}
            {(hasRatings || hasReviews || hasSuppliers) && (
              <>
                <GroupHeader title="Качество" colSpan={items.length + 1} />

                {hasRatings && (
                  <Row label="Рейтинг">
                    {items.map(item => {
                      const r = Number(item.stats?.rating || 0)
                      const isBest = r === maxRating && r > 0
                      return (
                        <Cell key={item.id} highlight={isBest}>
                          {r > 0 ? (
                            <div className="flex items-center gap-2">
                              <div className="flex items-center gap-0.5">
                                {[...Array(5)].map((_, i) => (
                                  <Star
                                    key={i}
                                    size={12}
                                    className={i < Math.round(r) ? 'fill-scout-warning text-scout-warning' : 'text-scout-subtle'}
                                  />
                                ))}
                              </div>
                              <span className="text-xs font-bold text-scout-text scout-tabnums">
                                {r.toFixed(1)}
                              </span>
                            </div>
                          ) : <Dash />}
                        </Cell>
                      )
                    })}
                  </Row>
                )}

                {hasReviews && (
                  <Row label="Отзывов">
                    {items.map(item => (
                      <Cell key={item.id}>
                        <span className="text-xs text-scout-text scout-tabnums">
                          {item.stats?.reviews_count || '—'}
                        </span>
                      </Cell>
                    ))}
                  </Row>
                )}

                {hasSuppliers && (
                  <Row label="Поставщик">
                    {items.map(item => (
                      <Cell key={item.id}>
                        {item.stats?.supplier ? (
                          <div>
                            <div className="text-xs text-scout-text truncate">{item.stats.supplier}</div>
                            {item.stats?.supplier_rating && (
                              <div className="text-[10px] text-scout-dim">
                                рейтинг {item.stats.supplier_rating}
                              </div>
                            )}
                          </div>
                        ) : <Dash />}
                      </Cell>
                    ))}
                  </Row>
                )}
              </>
            )}

            {/* ============ ВЫГОДА ============ */}
            {(hasSales || hasCashback) && (
              <>
                <GroupHeader title="Выгода" colSpan={items.length + 1} />

                {hasSales && (
                  <Row label="Скидка">
                    {items.map(item => (
                      <Cell key={item.id}>
                        {item.stats?.sale_percent ? (
                          <span className="text-xs font-bold text-scout-warning scout-tabnums">
                            {item.stats.sale_percent}%
                          </span>
                        ) : <Dash />}
                      </Cell>
                    ))}
                  </Row>
                )}

                {hasCashback && (
                  <Row label="Кэшбек">
                    {items.map(item => (
                      <Cell key={item.id}>
                        {item.stats?.cashback_percent ? (
                          <span className="text-xs font-bold text-scout-success scout-tabnums">
                            {item.stats.cashback_percent}%
                          </span>
                        ) : <Dash />}
                      </Cell>
                    ))}
                  </Row>
                )}
              </>
            )}

            {/* ============ ХАРАКТЕРИСТИКИ ============ */}
            {allSpecKeys.length > 0 && (
              <>
                <GroupHeader title="Характеристики" colSpan={items.length + 1} />
                {allSpecKeys.map(key => (
                  <Row key={key} label={prettyLabel(key)}>
                    {items.map(item => (
                      <Cell key={item.id}>
                        <span className="text-xs text-scout-text">
                          {formatSpec((item.specs as any)[key])}
                        </span>
                      </Cell>
                    ))}
                  </Row>
                ))}
              </>
            )}

            {/* ============ ПРЕДЛОЖЕНИЯ ============ */}
            {hasOffers && (
              <>
                <GroupHeader title="Предложения по магазинам" colSpan={items.length + 1} />
                <Row label="Доступно в">
                  {items.map(item => {
                    const offers = Object.entries(item.offers_by_source || {})
                    return (
                      <Cell key={item.id}>
                        {offers.length > 0 ? (
                          <div className="space-y-2">
                            {offers.map(([source, offer]) => (
                              <a
                                key={source}
                                href={offer.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="block p-2 bg-scout-bg rounded-scout border border-scout-subtle hover:border-scout-accent/60 transition-colors"
                              >
                                <div className="flex items-center justify-between gap-2">
                                  <span className="text-[10px] font-bold uppercase tracking-[0.08em] text-scout-text">
                                    {offer.source_display}
                                  </span>
                                  <ExternalLink size={10} className="text-scout-accent" />
                                </div>
                                <div className="text-xs text-scout-success font-bold mt-1 scout-tabnums">
                                  {formatPrice(Number(offer.price))}
                                </div>
                                {!offer.is_available && (
                                  <div className="text-[9px] text-scout-danger mt-1">
                                    Нет в наличии
                                  </div>
                                )}
                              </a>
                            ))}
                          </div>
                        ) : <Dash />}
                      </Cell>
                    )
                  })}
                </Row>
              </>
            )}

            {/* ============ ПЕРЕХОД ============ */}
            <Row label="">
              {items.map(item => (
                <Cell key={item.id}>
                  {item.best_offer?.url && (
                    <a
                      href={item.best_offer.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-scout border border-scout-accent/40 bg-scout-accent/10 px-3 py-1.5 text-[10px] uppercase tracking-[0.1em] text-scout-accent hover:bg-scout-accent/20 transition-colors"
                    >
                      В магазин <ExternalLink size={10} />
                    </a>
                  )}
                </Cell>
              ))}
            </Row>
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Dash() {
  return <span className="text-scout-dim text-xs">—</span>
}

function GroupHeader({ title, colSpan }: { title: string; colSpan: number }) {
  return (
    <tr className="bg-scout-bg border-t border-scout-border">
      <td colSpan={colSpan} className="px-3 py-2.5">
        <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-scout-accent">
          {title}
        </div>
      </td>
    </tr>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <tr className="border-t border-scout-subtle">
      <td className="sticky left-0 z-10 w-48 bg-scout-elevated border-r border-scout-subtle px-3 py-2.5 text-[10px] uppercase tracking-[0.1em] text-scout-dim align-top">
        {label}
      </td>
      {children}
    </tr>
  )
}

function Cell({ children, highlight }: { children: React.ReactNode; highlight?: boolean }) {
  return (
    <td
      className="border-r border-scout-subtle px-3 py-2.5 align-top w-56"
      style={highlight ? { background: 'rgba(168, 85, 247, 0.04)' } : undefined}
    >
      {children}
    </td>
  )
}

function pluralItems(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod100 >= 11 && mod100 <= 14) return 'товаров'
  if (mod10 === 1) return 'товар'
  if (mod10 >= 2 && mod10 <= 4) return 'товара'
  return 'товаров'
}

const LABEL_MAP: Record<string, string> = {
  rating: 'Рейтинг',
  reviews_count: 'Отзывы',
  brand: 'Бренд (источник)',
  brand_id: 'ID бренда',
  sale_percent: 'Скидка %',
  cashback_percent: 'Кэшбек %',
  supplier: 'Поставщик',
  supplier_rating: 'Рейтинг поставщика',
  ram_gb: 'ОЗУ, ГБ',
  storage_gb: 'Память, ГБ',
  color: 'Цвет',
  gpu_family: 'GPU',
  cpu_family: 'CPU',
  screen_in: 'Экран, дюймы',
  model_code: 'Модель',
  specs: 'Характеристики',
}

function prettyLabel(key: string) {
  return LABEL_MAP[key] || key.replace(/_/g, ' ')
}

function formatSpec(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'boolean') return v ? 'да' : 'нет'
  if (typeof v === 'object') {
    if (v && !Array.isArray(v)) {
      return Object.entries(v as Record<string, unknown>)
        .map(([k, val]) => `${prettyLabel(k)}: ${val}`)
        .join(', ')
    }
    return JSON.stringify(v).slice(0, 60)
  }
  return String(v)
}
