import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Package, Check } from 'lucide-react'
import * as Dialog from '@radix-ui/react-dialog'
import { motion, AnimatePresence } from 'framer-motion'
import { productsApi } from '@/api/products'
import { useDebounce } from '@/hooks/useDebounce'
import { formatPrice } from '@/lib/utils'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import type { Product } from '@/types'

interface Props {
  open: boolean
  onClose: () => void
  onSelect: (product: Product) => void
  categorySlug: string
  categoryLabel: string
}

/**
 * Большой модал-picker для выбора товара в слот сборки.
 * Поиск по названию + список с быстрой подгрузкой первых 50 товаров.
 */
export function BuilderSlotPicker({ open, onClose, onSelect, categorySlug, categoryLabel }: Props) {
  const [search, setSearch] = useState('')
  const debSearch = useDebounce(search, 350)

  const { data, isLoading } = useQuery({
    queryKey: ['builder-picker', categorySlug, debSearch],
    queryFn: () => productsApi.list({
      category_slug: categorySlug,
      search: debSearch,
      ordering: 'min_price',
      in_stock: true,
      page: 1,
      page_size: 50,
    }),
    enabled: open && !!categorySlug,
  })

  return (
    <Dialog.Root open={open} onOpenChange={v => !v && onClose()}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div
                className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              />
            </Dialog.Overlay>
            <Dialog.Content asChild>
              <motion.div
                className="fixed inset-0 z-50 flex items-center justify-center p-4"
                initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }}
              >
                <div className="w-full max-w-3xl max-h-[85vh] flex flex-col rounded-steam border border-steam-border bg-steam-card shadow-2xl">
                  <div className="flex items-center justify-between border-b border-steam-border px-4 py-3">
                    <Dialog.Title className="text-sm font-bold uppercase tracking-wider text-steam-light">
                      Выбор: {categoryLabel}
                    </Dialog.Title>
                  </div>

                  <div className="border-b border-steam-border p-3">
                    <Input
                      icon={<Search size={14} />}
                      placeholder={`Поиск в ${categoryLabel.toLowerCase()}...`}
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                      autoFocus
                    />
                  </div>

                  <div className="flex-1 overflow-y-auto">
                    {isLoading ? (
                      <div className="flex justify-center py-12"><Spinner /></div>
                    ) : !data?.results.length ? (
                      <div className="py-12 text-center text-steam-muted text-sm">Ничего не найдено</div>
                    ) : (
                      <ul className="divide-y divide-steam-border">
                        {data.results.map(p => {
                          const offer = p.best_offer
                          return (
                            <li key={p.id}>
                              <button
                                onClick={() => { onSelect(p); onClose() }}
                                className="flex w-full items-center gap-3 p-3 text-left hover:bg-steam-darker transition-colors"
                              >
                                <div className="h-14 w-14 shrink-0 rounded-steam bg-steam-darker flex items-center justify-center">
                                  {offer?.image_url ? (
                                    <img src={offer.image_url} alt={p.name} className="h-full w-full object-contain p-1" />
                                  ) : (
                                    <Package size={20} className="text-steam-border" />
                                  )}
                                </div>
                                <div className="flex-1 min-w-0">
                                  {p.brand && <span className="text-[9px] uppercase tracking-wider text-steam-muted">{p.brand}</span>}
                                  <div className="text-xs text-steam-light line-clamp-2">{p.name}</div>
                                </div>
                                <div className="flex flex-col items-end gap-1 shrink-0">
                                  {offer ? (
                                    <span className="text-sm font-bold text-steam-green">{formatPrice(Number(offer.price))}</span>
                                  ) : (
                                    <span className="text-xs text-steam-muted">Нет в наличии</span>
                                  )}
                                  <Check size={12} className="text-steam-blue opacity-0 group-hover:opacity-100" />
                                </div>
                              </button>
                            </li>
                          )
                        })}
                      </ul>
                    )}
                  </div>

                  <div className="border-t border-steam-border px-4 py-2 text-[10px] text-steam-muted">
                    Показано {data?.results.length ?? 0} из {data?.count ?? 0} (только в наличии, сначала дешевле)
                  </div>
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  )
}
