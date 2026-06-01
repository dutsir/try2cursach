import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { buildsApi, type Build } from '@/api/builds'

export type SlotKey = 'cpu' | 'mb' | 'gpu' | 'ram' | 'psu' | 'case' | 'ssd' | 'hdd'

/**
 * Состояние конструктора сборки ПК: для каждого слота — выбранный товар.
 * Хранится в localStorage через zustand persist.
 */
export interface BuildSlotItem {
  productId: number
  name: string
  brand: string
  imageUrl: string
  price: number
}

interface BuildState {
  ownerId: number | null
  slots: Partial<Record<SlotKey, BuildSlotItem>>
  setSlot: (slot: SlotKey, item: BuildSlotItem) => void
  clearSlot: (slot: SlotKey) => void
  clearAll: () => void
  totalPrice: () => number
  filledCount: () => number
  /** Привязывает сборку к юзеру; при смене аккаунта очищает чужую сборку. */
  ensureOwner: (userId: number | null) => void
  /** Загружает сборку с сервера и заменяет локальные слоты (для авторизованного юзера). */
  hydrateFromServer: () => Promise<void>
}

const SLOT_KEYS: SlotKey[] = ['cpu', 'mb', 'gpu', 'ram', 'psu', 'case', 'ssd', 'hdd']

function buildToSlots(build: Build): Partial<Record<SlotKey, BuildSlotItem>> {
  const slots: Partial<Record<SlotKey, BuildSlotItem>> = {}
  for (const item of build.items) {
    if (!SLOT_KEYS.includes(item.slot as SlotKey)) continue
    slots[item.slot as SlotKey] = {
      productId: item.product.id,
      name: item.product.name,
      brand: item.product.brand,
      imageUrl: item.product.best_offer?.image_url || '',
      price: Number(item.price_snapshot) || 0,
    }
  }
  return slots
}

export const useBuildStore = create<BuildState>()(
  persist(
    (set, get) => ({
      ownerId: null,
      slots: {},

      setSlot: (slot, item) => {
        set({ slots: { ...get().slots, [slot]: item } })
        // Write-through на сервер для авторизованного юзера (optimistic, без блокировки UI).
        if (get().ownerId !== null) {
          buildsApi.setSlot(slot, item.productId).catch(() => {})
        }
      },

      clearSlot: (slot) => {
        const next = { ...get().slots }
        delete next[slot]
        set({ slots: next })
        if (get().ownerId !== null) {
          buildsApi.clearSlot(slot).catch(() => {})
        }
      },

      clearAll: () => {
        set({ slots: {} })
        if (get().ownerId !== null) {
          buildsApi.clear().catch(() => {})
        }
      },

      totalPrice: () => {
        const slots = get().slots
        return Object.values(slots).reduce(
          (sum, item) => sum + (item?.price || 0), 0,
        )
      },

      filledCount: () => Object.keys(get().slots).length,

      ensureOwner: (userId) => {
        const cur = get().ownerId
        if (cur === userId) return
        // null = сборка ещё не привязана (старт/гость): присваиваем владельца,
        // НЕ стирая слоты. Чистим только при реальной смене аккаунта или выходе.
        if (cur === null) {
          set({ ownerId: userId })
          return
        }
        set({ ownerId: userId, slots: {} })
      },

      hydrateFromServer: async () => {
        try {
          const build = await buildsApi.mine()
          set({ slots: buildToSlots(build) })
        } catch {
          // нет сети/не авторизован — остаёмся на локальной сборке
        }
      },
    }),
    {
      name: 'pricewatch:build',
      version: 2,
    },
  ),
)
