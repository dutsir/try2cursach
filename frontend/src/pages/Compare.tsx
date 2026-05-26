import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { X, Package, ExternalLink, ArrowLeft, TrendingDown, TrendingUp, Star } from 'lucide-react'
import { compareApi, type CompareItem } from '@/api/compare'
import { useCompareStore } from '@/store/compare'
import { formatPrice, SOURCE_LABELS } from '@/lib/utils'
import { Spinner } from '@/components/ui/Spinner'
import { cn } from '@/lib/utils'

export default function Compare() {
  const [searchParams] = useSearchParams()
  const idsParam = searchParams.get('ids') || ''
  const ids = useMemo(
    () => idsParam.split(',').map(Number).filter(n => !isNaN(n) && n > 0),
    [idsParam],
  )

  const remove = useCompareStore(s => s.remove)

  const { data, isLoading } = useQuery({
    queryKey: ['compare', ids],
    queryFn: () => compareApi.get(ids),
    enabled: ids.length > 0,
  })

  if (!ids.length) {
    return (
      <div className="py-20 text-center">
        <p className="text-base text-steam-light mb-2">Нет товаров для сравнения</p>
        <Link to="/catalog" className="text-xs uppercase tracking-wider text-steam-blue hover:underline">
          Перейти в каталог
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
      <div className="py-20 text-center text-steam-muted">
        <p>Товары не найдены</p>
      </div>
    )
  }

  const allSpecKeys = Array.from(new Set(items.flatMap(i => Object.keys(i.specs || {}))))
    .filter(k => !['tokens'].includes(k))
    .sort()

  const maxValueScore = Math.max(...items.map(i => i.value_score || 0))

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link to="/catalog" className="flex items-center gap-1 text-xs uppercase tracking-wider text-steam-muted hover:text-steam-blue">
          <ArrowLeft size={12} /> К каталогу
        </Link>
        <h1 className="text-xl font-bold text-white">Сравнение товаров</h1>
        <span className="text-xs text-steam-muted">({items.length})</span>
      </div>

      <div className="space-y-3 overflow-x-auto rounded-steam border border-steam-border bg-steam-card">
        {/* Заголовок товаров */}
        <div className="flex sticky top-0 bg-steam-darker border-b border-steam-border">
          <div className="w-48 flex-shrink-0 border-r border-steam-border p-3" />
          {items.map(item => (
            <div key={item.id} className="w-56 flex-shrink-0 border-r border-steam-border p-3">
              <div className="flex items-start justify-between gap-2 mb-3">
                <Link to={`/products/${item.id}`} className="block flex-1">
                  {item.image_url || item.best_offer?.image_url ? (
                    <img
                      src={item.image_url || item.best_offer?.image_url}
                      alt={item.name}
                      className="h-24 w-full object-contain bg-steam-darker rounded-steam p-1"
                    />
                  ) : (
                    <div className="flex h-24 w-full items-center justify-center bg-steam-darker rounded-steam">
                      <Package size={32} className="text-steam-border" />
                    </div>
                  )}
                </Link>
                <button
                  onClick={() => remove(item.id)}
                  className="p-1 text-steam-muted hover:text-red-500 flex-shrink-0"
                  title="Убрать из сравнения"
                >
                  <X size={14} />
                </button>
              </div>
              <Link to={`/products/${item.id}`} className="text-xs font-medium text-steam-light line-clamp-2 hover:text-steam-blue block mb-1">
                {item.name}
              </Link>
              {item.brand && (
                <span className="text-[10px] uppercase tracking-wider text-steam-muted">{item.brand}</span>
              )}

              {/* Value Score */}
              <div className="mt-2 p-2 bg-steam-card rounded-steam border border-steam-border/50">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] uppercase tracking-wider text-steam-muted">Value Score</span>
                  <span className={cn(
                    'text-xs font-bold',
                    item.value_score === maxValueScore ? 'text-steam-green' : 'text-steam-light'
                  )}>
                    {item.value_score}%
                  </span>
                </div>
                <div className="w-full bg-steam-border rounded-full h-1">
                  <div
                    className="bg-steam-green h-1 rounded-full"
                    style={{ width: `${item.value_score}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Цена */}
        <Section title="Цена">
          {items.map(item => (
            <div key={item.id} className="w-56 flex-shrink-0 border-r border-steam-border p-3">
              {item.best_offer ? (
                <div className="space-y-2">
                  <div className="text-base font-bold text-steam-green">
                    {formatPrice(Number(item.best_offer.price))}
                  </div>
                  {item.best_offer.old_price && (
                    <div className="text-[10px] text-steam-muted line-through">
                      {formatPrice(Number(item.best_offer.old_price))}
                    </div>
                  )}
                  <div className="text-[10px] text-steam-muted">
                    {item.best_offer.source_display}
                  </div>

                  {/* Ценовой тренд */}
                  {item.price_trend && (
                    <div className="pt-2 border-t border-steam-border/30 flex items-center gap-2">
                      {item.price_trend.delta_pct < 0 ? (
                        <TrendingDown size={12} className="text-steam-green" />
                      ) : (
                        <TrendingUp size={12} className="text-red-500" />
                      )}
                      <span className={cn(
                        'text-[10px] font-mono',
                        item.price_trend.delta_pct < 0 ? 'text-steam-green' : 'text-red-500'
                      )}>
                        {item.price_trend.delta_pct > 0 ? '+' : ''}{item.price_trend.delta_pct}% (30d)
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <span className="text-steam-muted text-xs">—</span>
              )}
            </div>
          ))}
        </Section>

        {/* Качество */}
        <Section title="Качество">
          <Section title="Рейтинг" level={2}>
            {items.map(item => (
              <div key={item.id} className="w-56 flex-shrink-0 border-r border-steam-border p-3">
                {item.stats?.rating ? (
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1">
                      {[...Array(5)].map((_, i) => (
                        <Star
                          key={i}
                          size={12}
                          className={i < Math.round(Number(item.stats.rating) || 0) ? 'fill-steam-yellow text-steam-yellow' : 'text-steam-border'}
                        />
                      ))}
                    </div>
                    <span className="text-xs font-bold text-steam-light">{item.stats.rating}</span>
                  </div>
                ) : (
                  <span className="text-steam-muted text-xs">—</span>
                )}
              </div>
            ))}
          </Section>

          <Section title="Отзывы" level={2}>
            {items.map(item => (
              <div key={item.id} className="w-56 flex-shrink-0 border-r border-steam-border p-3">
                <span className="text-xs text-steam-light">
                  {item.stats?.reviews_count || '—'}
                </span>
              </div>
            ))}
          </Section>

          {/* Поставщик */}
          <Section title="Поставщик" level={2}>
            {items.map(item => (
              <div key={item.id} className="w-56 flex-shrink-0 border-r border-steam-border p-3 space-y-1">
                {item.stats?.supplier && (
                  <div className="text-xs text-steam-light truncate">{item.stats.supplier}</div>
                )}
                {item.stats?.supplier_rating && (
                  <div className="text-[10px] text-steam-muted">
                    Рейтинг: <span className="text-steam-light">{item.stats.supplier_rating}</span>
                  </div>
                )}
                {!item.stats?.supplier && <span className="text-steam-muted text-xs">—</span>}
              </div>
            ))}
          </Section>
        </Section>

        {/* Выгода */}
        <Section title="Выгода">
          <Section title="Скидка" level={2}>
            {items.map(item => (
              <div key={item.id} className="w-56 flex-shrink-0 border-r border-steam-border p-3">
                {item.stats?.sale_percent ? (
                  <span className="text-xs font-bold text-steam-yellow">{item.stats.sale_percent}%</span>
                ) : (
                  <span className="text-steam-muted text-xs">—</span>
                )}
              </div>
            ))}
          </Section>

          <Section title="Кэшбек" level={2}>
            {items.map(item => (
              <div key={item.id} className="w-56 flex-shrink-0 border-r border-steam-border p-3">
                {item.stats?.cashback_percent ? (
                  <span className="text-xs font-bold text-steam-green">{item.stats.cashback_percent}%</span>
                ) : (
                  <span className="text-steam-muted text-xs">—</span>
                )}
              </div>
            ))}
          </Section>
        </Section>

        {/* Доступные предложения */}
        <Section title="Предложения по источникам">
          {items.map(item => (
            <div key={item.id} className="w-56 flex-shrink-0 border-r border-steam-border p-3 space-y-2">
              {Object.entries(item.offers_by_source).map(([source, offer]) => (
                <a
                  key={source}
                  href={offer.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block p-2 bg-steam-darker rounded-steam border border-steam-border hover:border-steam-blue transition-colors text-[10px]"
                >
                  <div className="font-bold text-steam-light mb-1">{offer.source_display}</div>
                  <div className="text-steam-green font-mono">{formatPrice(Number(offer.price))}</div>
                  {!offer.is_available && (
                    <div className="text-red-500 text-[9px] mt-1">Нет в наличии</div>
                  )}
                </a>
              ))}
            </div>
          ))}
        </Section>

        {/* Характеристики */}
        {allSpecKeys.length > 0 && (
          <Section title="Характеристики">
            {allSpecKeys.map(key => (
              <Section key={key} title={prettyLabel(key)} level={2}>
                {items.map(item => (
                  <div key={item.id} className="w-56 flex-shrink-0 border-r border-steam-border p-3">
                    <span className="text-xs text-steam-light">{formatSpec((item.specs as any)[key])}</span>
                  </div>
                ))}
              </Section>
            ))}
          </Section>
        )}

        {/* Кнопки перехода */}
        <Section title="">
          {items.map(item => (
            <div key={item.id} className="w-56 flex-shrink-0 border-r border-steam-border p-3">
              {item.best_offer?.url && (
                <a
                  href={item.best_offer.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded-steam border border-steam-border px-3 py-1.5 text-[10px] uppercase tracking-wider text-steam-blue hover:bg-steam-darker"
                >
                  В магазин <ExternalLink size={10} />
                </a>
              )}
            </div>
          ))}
        </Section>
      </div>
    </div>
  )
}

interface SectionProps {
  title: string
  children: React.ReactNode
  level?: 1 | 2
}

function Section({ title, children, level = 1 }: SectionProps) {
  if (level === 2) {
    return (
      <div className="flex border-t border-steam-border">
        <div className="w-48 flex-shrink-0 border-r border-steam-border px-3 py-2 bg-steam-darker">
          <div className="text-[10px] uppercase tracking-wider text-steam-muted">{title}</div>
        </div>
        {children}
      </div>
    )
  }

  return (
    <div>
      <div className="flex border-t border-steam-border bg-steam-darker">
        <div className="w-48 flex-shrink-0 border-r border-steam-border px-3 py-3">
          <div className="text-xs font-bold uppercase tracking-wider text-steam-light">{title}</div>
        </div>
      </div>
      {children}
    </div>
  )
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
  source: 'Источник specs',
  specs: 'Структурированные specs',
}

function prettyLabel(key: string) {
  return LABEL_MAP[key] || key
}

function formatSpec(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'boolean') return v ? 'да' : 'нет'
  if (typeof v === 'object') return JSON.stringify(v).slice(0, 60)
  return String(v)
}
