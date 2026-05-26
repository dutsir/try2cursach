import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import {
  Cpu, CircuitBoard, Monitor, MemoryStick, Plug, Box, HardDrive,
  X,
} from 'lucide-react'
import { useBuildStore, type SlotKey } from '@/store/build'
import { BuilderSlotPicker } from '@/components/BuilderSlotPicker'
import { formatPrice } from '@/lib/utils'

interface SlotConfig {
  key: SlotKey
  label: string
  categorySlug: string
  icon: LucideIcon
  optional?: boolean
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

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-white">Конструктор ПК</h1>
          <p className="text-sm text-steam-muted mt-1">
            Выбирай компоненты — мы посчитаем суммарную цену в реальном времени.
          </p>
        </div>
        {filled > 0 && (
          <button
            onClick={clearAll}
            className="text-xs uppercase tracking-wider text-steam-muted hover:text-red-500 flex items-center gap-1"
          >
            <X size={12} /> Очистить сборку
          </button>
        )}
      </div>

      <div className="rounded-steam border border-steam-border bg-steam-card divide-y divide-steam-border">
        {PC_SLOTS.map(slot => {
          const Icon = slot.icon
          const item = slots[slot.key]
          return (
            <div key={slot.key} className="flex items-center gap-3 p-3">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-steam bg-steam-darker">
                <Icon size={20} className="text-steam-blue" />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs uppercase tracking-wider text-steam-muted">{slot.label}</span>
                  {slot.optional && <span className="text-[9px] text-steam-muted">(опционально)</span>}
                </div>
                {item ? (
                  <Link to={`/products/${item.productId}`} className="block text-sm text-steam-light hover:text-steam-blue mt-1 line-clamp-1">
                    {item.brand && <span className="font-semibold uppercase mr-1">{item.brand}</span>}
                    {item.name}
                  </Link>
                ) : (
                  <div className="text-sm text-steam-muted mt-1">Не выбрано</div>
                )}
              </div>

              {item ? (
                <>
                  <div className="text-right shrink-0">
                    <div className="text-sm font-bold text-steam-green">{formatPrice(item.price)}</div>
                  </div>
                  <button
                    onClick={() => setPicking(slot)}
                    className="rounded-steam border border-steam-border px-3 py-1.5 text-[10px] uppercase tracking-wider text-steam-muted hover:border-steam-blue hover:text-steam-blue"
                  >
                    Заменить
                  </button>
                  <button
                    onClick={() => clearSlot(slot.key)}
                    className="p-1.5 text-steam-muted hover:text-red-500"
                    title="Удалить из сборки"
                  >
                    <X size={14} />
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setPicking(slot)}
                  className="rounded-steam bg-steam-blue px-4 py-1.5 text-[10px] font-bold uppercase tracking-wider text-steam-darker hover:bg-steam-blue/90"
                >
                  Выбрать
                </button>
              )}
            </div>
          )
        })}
      </div>

      <div className="sticky bottom-0 z-20 -mx-4 lg:mx-0 border-t border-steam-border bg-steam-darker p-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3">
          <div className="flex flex-col">
            <span className="text-[10px] uppercase tracking-wider text-steam-muted">Итого</span>
            <span className="text-2xl font-bold text-steam-light">{formatPrice(total)}</span>
            <span className="text-[10px] text-steam-muted">{filled} из {PC_SLOTS.length} компонентов</span>
          </div>
          <div className="text-right text-[10px] text-steam-muted max-w-[200px]">
            Сборка сохраняется автоматически (в браузере). Проверка совместимости — в следующей версии.
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
