import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Heart, Plus, Trash2, AlertCircle, Edit2, ExternalLink } from 'lucide-react'
import { api } from '@/api/client'
import type { Wishlist, WishlistItem } from '@/types'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { PageSpinner } from '@/components/ui/Spinner'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/Toast'
import { formatPrice } from '@/lib/utils'
import { useDebounce } from '@/hooks/useDebounce'

interface ProductSearchResult {
  id: number
  name: string
  brand: string
  best_offer: { price: number; source: string } | null
}

export default function WishlistPage() {
  const [editTitle, setEditTitle] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [addItemOpen, setAddItemOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [note, setNote] = useState('')
  const [selectedProduct, setSelectedProduct] = useState<ProductSearchResult | null>(null)
  const qc = useQueryClient()
  const { toast } = useToast()

  const debouncedSearch = useDebounce(search, 400)

  const { data: wishlist, isLoading } = useQuery({
    queryKey: ['wishlist'],
    queryFn: () => api.get<Wishlist>('/api/wishlist/me/'),
  })

  const { data: searchResults } = useQuery({
    queryKey: ['products', 'search', debouncedSearch],
    queryFn: () =>
      api.get<{ results: ProductSearchResult[] }>('/api/products/', {
        search: debouncedSearch,
        page_size: 10,
      }),
    enabled: debouncedSearch.length > 1,
  })

  const addItemMutation = useMutation({
    mutationFn: () =>
      api.post('/api/wishlist/add_item/', {
        product_id: selectedProduct!.id,
        quantity: parseInt(quantity),
        note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wishlist'] })
      toast('Товар добавлен в вишлист', 'success')
      setAddItemOpen(false)
      setSearch('')
      setQuantity('1')
      setNote('')
      setSelectedProduct(null)
    },
    onError: () => toast('Ошибка при добавлении', 'error'),
  })

  const deleteItemMutation = useMutation({
    mutationFn: (itemId: number) => api.delete(`/api/wishlist/remove_item/${itemId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wishlist'] })
      toast('Товар удалён из вишлиста', 'info')
    },
  })

  const updateTitleMutation = useMutation({
    mutationFn: () => api.patch('/api/wishlist/me/', { title: newTitle }),
    onSuccess: (data) => {
      qc.setQueryData(['wishlist'], data)
      setEditTitle(false)
      toast('Название обновлено', 'success')
    },
  })

  if (isLoading) return <PageSpinner />

  const items = wishlist?.items ?? []
  const totalPrice = wishlist?.total_price ?? 0

  return (
    <>
      <div className="mb-8 flex flex-col gap-6">
        {/* Title */}
        <motion.div
          className="flex items-center justify-between"
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center gap-3">
            <Heart size={28} className="text-red-400 fill-red-400" />
            <div>
              {editTitle ? (
                <div className="flex gap-2">
                  <Input
                    value={newTitle}
                    onChange={e => setNewTitle(e.target.value)}
                    placeholder={wishlist?.title}
                    className="w-48"
                  />
                  <Button
                    size="sm"
                    onClick={() => updateTitleMutation.mutate()}
                    loading={updateTitleMutation.isPending}
                  >
                    Сохранить
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <h1 className="text-3xl font-bold text-white">{wishlist?.title}</h1>
                  <button
                    onClick={() => {
                      setNewTitle(wishlist?.title ?? '')
                      setEditTitle(true)
                    }}
                    className="text-white/40 hover:text-white transition"
                  >
                    <Edit2 size={18} />
                  </button>
                </div>
              )}
              <p className="text-sm text-white/50">{items.length} товаров на сумму {formatPrice(totalPrice)}</p>
            </div>
          </div>
          <Button onClick={() => setAddItemOpen(true)}>
            <Plus size={16} /> Добавить товар
          </Button>
        </motion.div>

        {/* Stats */}
        {items.length > 0 && (
          <motion.div
            className="grid grid-cols-2 gap-3 sm:grid-cols-3"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
          >
            <Card className="flex items-center justify-between p-4">
              <div>
                <p className="text-2xl font-bold text-white">{items.length}</p>
                <p className="text-xs text-white/50">Товаров</p>
              </div>
              <div className="text-3xl opacity-20">📦</div>
            </Card>
            <Card className="flex items-center justify-between p-4">
              <div>
                <p className="text-2xl font-bold text-white">{items.reduce((sum, i) => sum + i.quantity, 0)}</p>
                <p className="text-xs text-white/50">Единиц</p>
              </div>
              <div className="text-3xl opacity-20">🔢</div>
            </Card>
            <Card className="col-span-2 flex items-center justify-between p-4 sm:col-span-1">
              <div>
                <p className="text-lg font-bold text-white">{formatPrice(totalPrice)}</p>
                <p className="text-xs text-white/50">Сумма</p>
              </div>
              <div className="text-3xl opacity-20">💰</div>
            </Card>
          </motion.div>
        )}
      </div>

      {/* Items list */}
      {items.length === 0 ? (
        <motion.div
          className="flex flex-col items-center gap-4 py-24 text-white/40"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <Heart size={56} strokeWidth={1} />
          <p className="text-xl font-medium">Вишлист пуст</p>
          <p className="text-sm">Добавьте товары, которые хотите купить позже</p>
          <Button onClick={() => setAddItemOpen(true)} className="mt-2">
            <Plus size={16} /> Добавить товар
          </Button>
        </motion.div>
      ) : (
        <div className="flex flex-col gap-3">
          <AnimatePresence>
            {items.map((item, i) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ delay: i * 0.05 }}
              >
                <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
                  <div className="flex-1 min-w-0">
                    <h3 className="truncate font-semibold text-white">{item.product.name}</h3>
                    {item.product.brand && (
                      <p className="text-xs text-white/40">{item.product.brand}</p>
                    )}
                    {item.note && (
                      <p className="mt-2 text-sm text-white/60 italic">{item.note}</p>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-4 sm:justify-end">
                    {item.product.best_offer && (
                      <div>
                        <p className="text-right text-sm text-white/60">Цена за единицу</p>
                        <p className="text-lg font-bold text-white">{formatPrice(item.product.best_offer.price)}</p>
                        <Badge variant="ghost" className="mt-1">
                          {item.product.best_offer.source}
                        </Badge>
                      </div>
                    )}

                    <div>
                      <p className="text-right text-sm text-white/60">Количество</p>
                      <p className="text-lg font-bold text-white">{item.quantity}</p>
                    </div>

                    {item.product.best_offer && (
                      <div>
                        <p className="text-right text-sm text-white/60">Сумма</p>
                        <p className="text-lg font-bold text-brand-300">
                          {formatPrice(item.product.best_offer.price * item.quantity)}
                        </p>
                      </div>
                    )}

                    <div className="flex shrink-0 gap-1">
                      {item.product.best_offer?.url && (
                        <a
                          href={item.product.best_offer.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="rounded-lg p-1.5 text-white/40 transition hover:bg-white/10 hover:text-white"
                        >
                          <ExternalLink size={15} />
                        </a>
                      )}
                      <Button
                        size="icon"
                        variant="danger"
                        loading={deleteItemMutation.isPending}
                        onClick={() => deleteItemMutation.mutate(item.id)}
                      >
                        <Trash2 size={15} />
                      </Button>
                    </div>
                  </div>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Add item modal */}
      <Modal open={addItemOpen} onClose={() => setAddItemOpen(false)} title="Добавить товар в вишлист">
        <div className="flex flex-col gap-4">
          <Input
            placeholder="Поиск товара..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />

          {debouncedSearch.length > 1 && (
            <div className="max-h-56 overflow-y-auto rounded-xl border border-white/10 bg-white/5">
              {searchResults?.results && searchResults.results.length > 0 ? (
                <ul>
                  {searchResults.results.map(product => (
                    <li key={product.id}>
                      <button
                        onClick={() => {
                          setSelectedProduct(product)
                          setSearch(product.name)
                        }}
                        className="flex w-full items-start gap-3 px-4 py-3 text-left transition hover:bg-white/10"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="truncate font-medium text-white">{product.name}</p>
                          {product.brand && (
                            <p className="text-xs text-white/40">{product.brand}</p>
                          )}
                        </div>
                        {product.best_offer && (
                          <p className="shrink-0 font-semibold text-white">
                            {formatPrice(product.best_offer.price)}
                          </p>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="px-4 py-6 text-center text-sm text-white/40">
                  Ничего не найдено
                </div>
              )}
            </div>
          )}

          {selectedProduct && (
            <div className="flex items-center gap-2 rounded-lg bg-brand-600/20 px-4 py-3">
              <div className="flex-1">
                <p className="font-semibold text-white">{selectedProduct.name}</p>
                {selectedProduct.best_offer && (
                  <p className="text-sm text-brand-300">{formatPrice(selectedProduct.best_offer.price)}</p>
                )}
              </div>
            </div>
          )}

          <div>
            <label className="text-xs font-medium text-white/60">Количество</label>
            <Input
              type="number"
              min="1"
              value={quantity}
              onChange={e => setQuantity(e.target.value)}
              className="mt-1.5"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-white/60">Заметка (опционально)</label>
            <textarea
              value={note}
              onChange={e => setNote(e.target.value)}
              className="mt-1.5 w-full rounded-xl border border-white/15 bg-white/10 px-4 py-2.5 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
              rows={2}
              placeholder="Например, нужна версия 16 ГБ..."
            />
          </div>

          <Button
            className="w-full"
            disabled={!selectedProduct || !quantity || parseInt(quantity) < 1}
            loading={addItemMutation.isPending}
            onClick={() => addItemMutation.mutate()}
          >
            <Plus size={16} /> Добавить в вишлист
          </Button>
        </div>
      </Modal>
    </>
  )
}
