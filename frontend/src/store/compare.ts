import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const MAX_ITEMS = 4

interface CompareState {
  ids: number[]
  add: (id: number) => { ok: boolean; reason?: string }
  remove: (id: number) => void
  toggle: (id: number) => { ok: boolean; reason?: string }
  clear: () => void
  has: (id: number) => boolean
}

export const useCompareStore = create<CompareState>()(
  persist(
    (set, get) => ({
      ids: [],

      add: (id) => {
        const cur = get().ids
        if (cur.includes(id)) return { ok: true }
        if (cur.length >= MAX_ITEMS) {
          return { ok: false, reason: `Можно сравнивать не более ${MAX_ITEMS} товаров` }
        }
        set({ ids: [...cur, id] })
        return { ok: true }
      },

      remove: (id) => {
        set({ ids: get().ids.filter(x => x !== id) })
      },

      toggle: (id) => {
        const cur = get().ids
        if (cur.includes(id)) {
          set({ ids: cur.filter(x => x !== id) })
          return { ok: true }
        }
        return get().add(id)
      },

      clear: () => set({ ids: [] }),

      has: (id) => get().ids.includes(id),
    }),
    {
      name: 'pricewatch:compare',
      version: 1,
    },
  ),
)

export { MAX_ITEMS as COMPARE_MAX }
