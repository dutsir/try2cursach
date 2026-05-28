import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Package, X } from 'lucide-react'
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
                className="fixed inset-0 z-40 bg-black/70 backdrop-blur-md"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              />
            </Dialog.Overlay>
            <Dialog.Content asChild>
              <motion.div
                className="fixed inset-0 z-50 flex items-center justify-center p-4"
                initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }}
                transition={{ duration: 0.2 }}
              >
                <div className="w-full max-w-3xl max-h-[85vh] flex flex-col rounded-scout-xl border border-scout-border bg-scout-elevated shadow-[0_24px_80px_rgba(0,0,0,0.6)]">
                  <div className="flex items-start justify-between border-b border-scout-subtle px-6 py-4">
                    <div>
                      <div className="scout-caption">new slot</div>
                      <Dialog.Title className="mt-1 font-display text-[24px] font-bold tracking-[-0.02em] lowercase text-scout-text">
                        {categoryLabel.toLowerCase()}
                      </Dialog.Title>
                    </div>
                    <button
                      onClick={onClose}
                      className="w-8 h-8 rounded-scout text-scout-muted hover:bg-scout-subtle hover:text-scout-text border border-scout-subtle flex items-center justify-center transition-colors"
                    >
                      <X size={14} />
                    </button>
                  </div>

                  <div className="border-b border-scout-subtle p-4">
                    <Input
                      icon={<Search size={14} />}
                      placeholder={`Поиск в ${categoryLabel.toLowerCase()}…`}
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                      autoFocus
                    />
                  </div>

                  <div className="flex-1 overflow-y-auto">
                    {isLoading ? (
                      <div className="flex justify-center py-12"><Spinner /></div>
                    ) : !data?.results.length ? (
                      <div className="py-12 text-center text-scout-muted text-sm">Ничего не найдено</div>
                    ) : (
                      <ul className="divide-y divide-scout-subtle">
                        {data.results.map(p => {
                          const offer = p.best_offer
                          return (
                            <li key={p.id}>
                              <button
                                onClick={() => { onSelect(p); onClose() }}
                                className="flex w-full items-center gap-3 p-4 text-left hover:bg-scout-subtle/40 transition-colors"
                              >
                                <div className="h-14 w-14 shrink-0 rounded-scout bg-scout-bg flex items-center justify-center border border-scout-subtle">
                                  {offer?.image_url ? (
                                    <img src={offer.image_url} alt={p.name} className="h-full w-full object-contain p-1" />
                                  ) : (
                                    <Package size={20} className="text-scout-dim" />
                                  )}
                                </div>
                                <div className="flex-1 min-w-0">
                                  {p.brand && (
                                    <span className="text-[10px] uppercase tracking-[0.08em] text-scout-dim">{p.brand}</span>
                                  )}
                                  <div className="text-[13px] text-scout-text line-clamp-2">{p.name}</div>
                                </div>
                                <div className="flex flex-col items-end gap-1 shrink-0">
                                  {offer ? (
                                    <span className="text-sm font-bold text-scout-accent scout-tabnums">
                                      {formatPrice(Number(offer.price))}
                                    </span>
                                  ) : (
                                    <span className="text-xs text-scout-dim">Нет в наличии</span>
                                  )}
                                </div>
                              </button>
                            </li>
                          )
                        })}
                      </ul>
                    )}
                  </div>

                  <div className="border-t border-scout-subtle px-6 py-3 text-[10px] text-scout-dim uppercase tracking-[0.08em]">
                    показано <span className="scout-tabnums text-scout-muted">{data?.results.length ?? 0}</span> из <span className="scout-tabnums text-scout-muted">{data?.count ?? 0}</span> · только в наличии, сначала дешевле
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
