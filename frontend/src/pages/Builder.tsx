import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import {
  Cpu, CircuitBoard, Monitor, MemoryStick, Plug, Box, HardDrive, X, Wand2, Loader2,
} from 'lucide-react'
import { useBuildStore, type SlotKey } from '@/store/build'
import { BuilderSlotPicker } from '@/components/BuilderSlotPicker'
import { productsApi } from '@/api/products'
import { formatPrice } from '@/lib/utils'
import type { Product } from '@/types'

interface SlotConfig {
  key: SlotKey
  label: string
  categorySlug: string
  icon: LucideIcon
  optional?: boolean
}

/**
 * «Идеальный» вариант для слота: в наличии + с фото важнее всего, а среди таких —
 * товар с ценой ближе всего к медиане категории (не дно и не топ). Если товаров
 * с фото нет — берём ближайший к медиане из всех, чтобы слот всё равно заполнился.
 */
function pickIdeal(products: Product[]): Product | null {
  const priced = products.filter(p => p.best_offer && Number(p.best_offer.price) > 0)
  if (!priced.length) return null
  const withPhoto = priced.filter(p => !!p.best_offer!.image_url)
  const pool = withPhoto.length ? withPhoto : priced
  const prices = pool.map(p => Number(p.best_offer!.price)).sort((a, b) => a - b)
  const median = prices[Math.floor(prices.length / 2)]
  return pool.reduce((best, p) =>
    Math.abs(Number(p.best_offer!.price) - median) < Math.abs(Number(best.best_offer!.price) - median)
      ? p : best,
  )
}

const PC_SLOTS: SlotConfig[] = [
  { key: 'cpu',  label: 'Процессор',          categorySlug: 'processory',          icon: Cpu },
  { key: 'mb',   label: 'Материнская плата',  categorySlug: 'materinskie-platy',   icon: CircuitBoard },
  { key: 'gpu',  label: 'Видеокарта',         categorySlug: 'videokarty',          icon: Monitor },
  { key: 'ram',  label: 'Оперативная память', categorySlug: 'operativnaya-pamyat', icon: MemoryStick },
  { key: 'psu',  label: 'Блок питания',       categorySlug: 'bloki-pitaniya',      icon: Plug },
  { key: 'case', label: 'Корпус',             categorySlug: 'korpusa',             icon: Box },
  { key: 'ssd',  label: 'SSD',                categorySlug: 'ssd-nakopiteli',      icon: HardDrive },
  { key: 'hdd',  label: 'Жёсткий диск',       categorySlug: 'zhestkie-diski-35',   icon: HardDrive, optional: true },
]

export default function Builder() {
  const slots = useBuildStore(s => s.slots)
  const setSlot = useBuildStore(s => s.setSlot)
  const clearSlot = useBuildStore(s => s.clearSlot)
  const clearAll = useBuildStore(s => s.clearAll)
  const total = useBuildStore(s => s.totalPrice())
  const filled = useBuildStore(s => s.filledCount())

  const [picking, setPicking] = useState<SlotConfig | null>(null)
  const [building, setBuilding] = useState(false)
  const progressPct = (filled / PC_SLOTS.length) * 100

  // Заполняем только пустые обязательные слоты — ручной выбор не перетираем.
  const emptyRequired = PC_SLOTS.filter(s => !s.optional && !slots[s.key])

  const autoBuild = async () => {
    if (building || !emptyRequired.length) return
    setBuilding(true)
    try {
      await Promise.all(emptyRequired.map(async (slot) => {
        try {
          const res = await productsApi.list({
            category_slug: slot.categorySlug,
            in_stock: true,
            ordering: 'min_price',
            page: 1,
            page_size: 100,
          })
          const pick = pickIdeal(res.results)
          if (!pick) return
          const offer = pick.best_offer
          setSlot(slot.key, {
            productId: pick.id,
            name: pick.name,
            brand: pick.brand || '',
            imageUrl: offer?.image_url || '',
            price: Number(offer?.price || 0),
          })
        } catch {
          // слот, который не удалось подобрать, просто пропускаем
        }
      }))
    } finally {
      setBuilding(false)
    }
  }

  return (
    <div className="animate-scout-rise space-y-6 pb-24">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="scout-caption">build your pc</div>
          <h1 className="mt-2 font-display text-[40px] font-bold tracking-[-0.02em] lowercase text-scout-text">
            конструктор пк.
          </h1>
          <p className="mt-2 text-sm text-scout-muted max-w-[560px]">
            выбирай компоненты — мы посчитаем суммарную цену в реальном времени. сборка сохраняется автоматически в браузере.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={autoBuild}
            disabled={building || emptyRequired.length === 0}
            title={emptyRequired.length === 0 ? 'Все обязательные слоты заполнены' : 'Подобрать сбалансированные варианты в пустые слоты'}
            className="flex items-center gap-1.5 rounded-scout bg-scout-accent/10 border border-scout-accent/30 px-3 py-1.5 text-[11px] uppercase tracking-[0.1em] text-scout-accent hover:bg-scout-accent/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {building ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />}
            {building ? 'подбираем…' : 'собрать за меня'}
          </button>
          {filled > 0 && (
            <button
              onClick={clearAll}
              className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.1em] text-scout-dim hover:text-scout-danger transition-colors"
            >
              <X size={12} /> очистить сборку
            </button>
          )}
        </div>
      </div>

      {/* Progress strip */}
      <div className="flex items-center gap-4 p-4 rounded-scout-lg bg-scout-elevated border border-scout-subtle">
        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <span className="scout-caption">прогресс сборки</span>
            <span className="text-xs text-scout-muted scout-tabnums">
              {filled} / {PC_SLOTS.length}
            </span>
          </div>
          <div className="h-1 bg-scout-subtle rounded-full overflow-hidden">
            <div
              className="h-full bg-scout-accent transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Slots */}
      <div className="rounded-scout-lg border border-scout-subtle bg-scout-elevated divide-y divide-scout-subtle overflow-hidden">
        {PC_SLOTS.map(slot => {
          const Icon = slot.icon
          const item = slots[slot.key]
          return (
            <div key={slot.key} className="flex items-center gap-4 p-4 transition-colors hover:bg-scout-subtle/30">
              <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-scout border ${
                item ? 'bg-scout-accent/10 border-scout-accent/30' : 'bg-scout-bg border-scout-subtle'
              }`}>
                <Icon size={20} className={item ? 'text-scout-accent' : 'text-scout-dim'} />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] uppercase tracking-[0.1em] text-scout-dim">{slot.label}</span>
                  {slot.optional && (
                    <span className="text-[9px] uppercase tracking-[0.08em] text-scout-dim">(опционально)</span>
                  )}
                </div>
                {item ? (
                  <Link to={`/products/${item.productId}`} className="block text-[14px] text-scout-text hover:text-scout-accent mt-1 line-clamp-1 transition-colors">
                    {item.brand && <span className="font-semibold uppercase mr-1.5 text-scout-muted">{item.brand}</span>}
                    {item.name}
                  </Link>
                ) : (
                  <div className="text-[13px] text-scout-dim mt-1">Не выбрано</div>
                )}
              </div>

              {item ? (
                <>
                  <div className="text-right shrink-0">
                    <div className="text-sm font-bold text-scout-accent scout-tabnums">{formatPrice(item.price)}</div>
                  </div>
                  <button
                    onClick={() => setPicking(slot)}
                    className="scout-btn-ghost h-8 text-[11px] px-3"
                  >
                    заменить
                  </button>
                  <button
                    onClick={() => clearSlot(slot.key)}
                    className="p-1.5 text-scout-dim hover:text-scout-danger transition-colors"
                    title="Удалить из сборки"
                  >
                    <X size={14} />
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setPicking(slot)}
                  className="scout-btn-primary h-8 text-[11px] px-4"
                >
                  выбрать
                </button>
              )}
            </div>
          )
        })}
      </div>

      {/* Sticky total */}
      <div className="sticky bottom-0 z-20 -mx-6 lg:-mx-10 border-t border-scout-subtle bg-scout-elevated/95 backdrop-blur-md">
        <div className="flex flex-wrap items-center justify-between gap-3 px-6 lg:px-10 py-4">
          <div>
            <div className="scout-caption">итого</div>
            <div className="mt-1 font-display text-[32px] font-bold tracking-[-0.02em] text-scout-text scout-tabnums leading-none">
              {formatPrice(total)}
            </div>
            <div className="mt-1 text-[11px] text-scout-muted">
              {filled} из {PC_SLOTS.length} компонентов
            </div>
          </div>
          <div className="text-right text-[10px] text-scout-dim max-w-[260px]">
            сборка сохраняется автоматически в браузере. проверка совместимости — в следующей версии.
          </div>
        </div>
      </div>

      {picking && (
        <BuilderSlotPicker
          open={!!picking}
          onClose={() => setPicking(null)}
          categorySlug={picking.categorySlug}
          categoryLabel={picking.label}
          onSelect={(product) => {
            const offer = product.best_offer
            setSlot(picking.key, {
              productId: product.id,
              name: product.name,
              brand: product.brand || '',
              imageUrl: offer?.image_url || '',
              price: Number(offer?.price || 0),
            })
          }}
        />
      )}
    </div>
  )
}
