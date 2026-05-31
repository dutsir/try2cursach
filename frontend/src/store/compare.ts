import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const MAX_ITEMS = 4

interface CompareState {
  ownerId: number | null
  ids: number[]
  add: (id: number) => { ok: boolean; reason?: string }
  remove: (id: number) => void
  toggle: (id: number) => { ok: boolean; reason?: string }
  clear: () => void
  has: (id: number) => boolean
  /** Привязывает список к юзеру; при смене аккаунта очищает чужой список. */
  ensureOwner: (userId: number | null) => void
}

export const useCompareStore = create<CompareState>()(
  persist(
    (set, get) => ({
      ownerId: null,
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

      ensureOwner: (userId) => {
        const cur = get().ownerId
        if (cur === userId) return
        // null = список ещё не привязан (старт/гость): присваиваем владельца,
        // НЕ стирая выбранное. Иначе гонка с initAuth затирала свежий выбор.
        // Чистим только при реальной смене аккаунта или выходе.
        if (cur === null) {
          set({ ownerId: userId })
          return
        }
        set({ ownerId: userId, ids: [] })
      },
    }),
    {
      name: 'pricewatch:compare',
      version: 2,
    },
  ),
)

export { MAX_ITEMS as COMPARE_MAX }
