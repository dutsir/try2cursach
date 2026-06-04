import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const MAX_ITEMS = 4

/** Краткая категория товара — нужна, чтобы держать сравнение в рамках одной категории. */
export interface CompareCategory {
  id: number
  name: string
}

interface CompareState {
  ownerId: number | null
  ids: number[]
  /** Категория, к которой «привязан» текущий список. null = список пуст. */
  categoryId: number | null
  categoryName: string | null
  add: (id: number, category: CompareCategory) => { ok: boolean; reason?: string }
  remove: (id: number) => void
  toggle: (id: number, category: CompareCategory) => { ok: boolean; reason?: string }
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
      categoryId: null,
      categoryName: null,

      add: (id, category) => {
        const { ids, categoryId, categoryName } = get()
        if (ids.includes(id)) return { ok: true }
        if (ids.length >= MAX_ITEMS) {
          return { ok: false, reason: `Можно сравнивать не более ${MAX_ITEMS} товаров` }
        }
        // Первый товар задаёт категорию списка; дальше пускаем только её же.
        if (ids.length && categoryId !== null && category.id !== categoryId) {
          return {
            ok: false,
            reason: `Сравнивать можно только товары одной категории (выбрана «${categoryName}»). Очисти сравнение, чтобы начать заново.`,
          }
        }
        set({
          ids: [...ids, id],
          categoryId: category.id,
          categoryName: category.name,
        })
        return { ok: true }
      },

      remove: (id) => {
        const next = get().ids.filter(x => x !== id)
        set(next.length
          ? { ids: next }
          : { ids: next, categoryId: null, categoryName: null })
      },

      toggle: (id, category) => {
        const cur = get().ids
        if (cur.includes(id)) {
          get().remove(id)
          return { ok: true }
        }
        return get().add(id, category)
      },

      clear: () => set({ ids: [], categoryId: null, categoryName: null }),

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
        set({ ownerId: userId, ids: [], categoryId: null, categoryName: null })
      },
    }),
    {
      name: 'pricewatch:compare',
      version: 3,
    },
  ),
)

export { MAX_ITEMS as COMPARE_MAX }
