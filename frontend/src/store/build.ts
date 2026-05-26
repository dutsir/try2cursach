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
  slots: Partial<Record<SlotKey, BuildSlotItem>>
  setSlot: (slot: SlotKey, item: BuildSlotItem) => void
  clearSlot: (slot: SlotKey) => void
  clearAll: () => void
  totalPrice: () => number
  filledCount: () => number
}

export const useBuildStore = create<BuildState>()(
  persist(
    (set, get) => ({
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
    }),
    {
      name: 'pricewatch:build',
      version: 1,
    },
  ),
)
