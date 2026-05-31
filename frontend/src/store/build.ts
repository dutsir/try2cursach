import { create } from 'zustand'
import { persist } from 'zustand/middleware'

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
}

export const useBuildStore = create<BuildState>()(
  persist(
    (set, get) => ({
      ownerId: null,
      slots: {},

      setSlot: (slot, item) =>
        set({ slots: { ...get().slots, [slot]: item } }),

      clearSlot: (slot) => {
        const next = { ...get().slots }
        delete next[slot]
        set({ slots: next })
      },

      clearAll: () => set({ slots: {} }),

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
    }),
    {
      name: 'pricewatch:build',
      version: 2,
    },
  ),
)
