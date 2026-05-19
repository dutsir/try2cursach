import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, ExternalLink, Edit2 } from 'lucide-react'
import { api } from '@/api/client'
import type { Wishlist, WishlistItem } from '@/types'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { PageSpinner } from '@/components/ui/Spinner'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/Toast'
import { cn, formatPrice, formatRelativeDate } from '@/lib/utils'
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
    mutationFn: (itemId: number) => api.delete(`/api/wishlist/remove-item/${itemId}/`),
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

  const rawItems: WishlistItem[] = wishlist?.items ?? []
  const items = [...rawItems].sort((a, b) => {
    const aAvail = a.product.best_offer ? 1 : 0
    const bAvail = b.product.best_offer ? 1 : 0
    if (aAvail !== bAvail) return bAvail - aAvail
    return new Date(b.added_at).getTime() - new Date(a.added_at).getTime()
  })
  const totalPrice = wishlist?.total_price ?? 0
  const totalUnits = items.reduce((sum, i) => sum + i.quantity, 0)
  const availableCount = items.filter(i => i.product.best_offer).length
  const unavailableCount = items.length - availableCount

  return (
    <>
      <div className="mb-6">
        <div className="flex items-center justify-between gap-4">
          {editTitle ? (
            <div className="flex flex-1 gap-2">
              <Input
                value={newTitle}
                onChange={e => setNewTitle(e.target.value)}
                placeholder={wishlist?.title}
                className="max-w-xs"
              />
              <Button size="sm" onClick={() => updateTitleMutation.mutate()} loading={updateTitleMutation.isPending}>
                Сохранить
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setEditTitle(false)}>
                Отмена
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-white">{wishlist?.title || 'Мой вишлист'}</h1>
              <button
                onClick={() => { setNewTitle(wishlist?.title ?? ''); setEditTitle(true) }}
                className="text-steam-muted hover:text-steam-blue transition-colors"
                title="Изменить название"
              >
                <Edit2 size={15} />
              </button>
            </div>
          )}
          <Button variant="green" onClick={() => setAddItemOpen(true)}>
            <Plus size={14} /> Добавить товар
          </Button>
        </div>
        <div className="h-px bg-steam-border mt-3" />

        {items.length > 0 && (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="bg-steam-card border border-steam-border rounded-steam p-3">
              <p className="text-[10px] uppercase tracking-wider text-steam-muted">Товаров</p>
              <p className="text-xl font-bold text-steam-light mt-1">{items.length}</p>
            </div>
            <div className="bg-steam-card border border-steam-border rounded-steam p-3">
              <p className="text-[10px] uppercase tracking-wider text-steam-muted">Единиц</p>
              <p className="text-xl font-bold text-steam-light mt-1">{totalUnits}</p>
            </div>
            <div className="bg-steam-card border border-steam-border rounded-steam p-3">
              <p className="text-[10px] uppercase tracking-wider text-steam-muted">В наличии</p>
              <p className="text-xl font-bold text-steam-light mt-1">
                <span className="text-steam-green">{availableCount}</span>
                {unavailableCount > 0 && (
                  <span className="text-steam-muted text-sm font-normal"> / {items.length}</span>
                )}
              </p>
            </div>
            <div className="bg-steam-card border border-steam-border rounded-steam p-3">
              <p className="text-[10px] uppercase tracking-wider text-steam-muted">Сумма</p>
              <p className="text-xl font-bold text-steam-green mt-1">{formatPrice(totalPrice)}</p>
            </div>
          </div>
        )}
      </div>

      {items.length === 0 ? (
        <div className="bg-steam-card border border-steam-border rounded-steam py-16 flex flex-col items-center gap-3 text-steam-muted">
          <p className="text-base text-steam-light">Вишлист пуст</p>
          <p className="text-xs">Добавьте товары, которые хотите купить позже</p>
          <Button variant="green" className="mt-2" onClick={() => setAddItemOpen(true)}>
            <Plus size={14} /> Добавить товар
          </Button>
        </div>
      ) : (
        <div className="flex flex-col">
          {items.map((item) => {
            const available = !!item.product.best_offer
            return (
              <div
                key={item.id}
                className={cn(
                  'bg-steam-card border rounded-steam mb-2 p-3 flex flex-col gap-3 sm:flex-row sm:items-center transition-colors',
                  available
                    ? 'border-steam-border hover:border-steam-blue/40'
                    : 'border-steam-border/40 opacity-60',
                )}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm font-semibold text-steam-light truncate">{item.product.name}</h3>
                    {!available && (
                      <Badge variant="danger">Нет в наличии</Badge>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-3 mt-0.5">
                    {item.product.brand && (
                      <p className="text-[10px] uppercase tracking-wider text-steam-muted">{item.product.brand}</p>
                    )}
                    <p className="text-[10px] text-steam-dim" title={item.added_at}>
                      Добавлен {formatRelativeDate(item.added_at)}
                    </p>
                  </div>
                  {item.note && (
                    <p className="mt-2 text-xs text-steam-muted italic border-l-2 border-steam-border pl-2">{item.note}</p>
                  )}
                </div>

                <div className="flex flex-wrap items-center justify-between gap-5 sm:justify-end">
                  {item.product.best_offer ? (
                    <div className="text-right">
                      <p className="text-[10px] uppercase tracking-wider text-steam-muted">Цена</p>
                      <p className="text-sm font-bold text-steam-light">{formatPrice(item.product.best_offer.price)}</p>
                      <Badge variant="ghost" className="mt-0.5">{item.product.best_offer.source}</Badge>
                    </div>
                  ) : (
                    <div className="text-right">
                      <p className="text-[10px] uppercase tracking-wider text-steam-muted">Цена</p>
                      <p className="text-sm text-steam-dim">—</p>
                    </div>
                  )}

                  <div className="text-right">
                    <p className="text-[10px] uppercase tracking-wider text-steam-muted">Кол-во</p>
                    <p className="text-sm font-bold text-steam-light">{item.quantity}</p>
                  </div>

                  <div className="text-right">
                    <p className="text-[10px] uppercase tracking-wider text-steam-muted">Сумма</p>
                    <p className={cn(
                      'text-sm font-bold',
                      available ? 'text-steam-green' : 'text-steam-dim',
                    )}>
                      {item.product.best_offer
                        ? formatPrice(item.product.best_offer.price * item.quantity)
                        : '—'}
                    </p>
                  </div>

                  <div className="flex items-center gap-1">
                    {item.product.best_offer?.url && (
                      <a
                        href={item.product.best_offer.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Открыть в магазине"
                        className="p-1.5 rounded-steam text-steam-muted hover:bg-steam-panel hover:text-steam-blue transition-colors"
                      >
                        <ExternalLink size={14} />
                      </a>
                    )}
                    <button
                      onClick={() => deleteItemMutation.mutate(item.id)}
                      disabled={deleteItemMutation.isPending}
                      title="Удалить из вишлиста"
                      className="p-1.5 rounded-steam text-steam-muted hover:bg-[#5a1a1a] hover:text-white transition-colors disabled:opacity-50"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <Modal open={addItemOpen} onClose={() => setAddItemOpen(false)} title="Добавить товар в вишлист">
        <div className="flex flex-col gap-4">
          <Input
            placeholder="Поиск товара..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />

          {debouncedSearch.length > 1 && (
            <div className="max-h-56 overflow-y-auto border border-steam-border rounded-steam bg-steam-darker">
              {searchResults?.results && searchResults.results.length > 0 ? (
                <ul>
                  {searchResults.results.map(product => (
                    <li key={product.id}>
                      <button
                        onClick={() => { setSelectedProduct(product); setSearch(product.name) }}
                        className="flex w-full items-start gap-3 px-3 py-2.5 text-left transition-colors hover:bg-steam-panel border-b border-steam-border/50 last:border-0"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="truncate text-sm font-medium text-steam-light">{product.name}</p>
                          {product.brand && (
                            <p className="text-[10px] uppercase tracking-wider text-steam-muted">{product.brand}</p>
                          )}
                        </div>
                        {product.best_offer && (
                          <p className="shrink-0 text-sm font-bold text-steam-green">
                            {formatPrice(product.best_offer.price)}
                          </p>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="px-4 py-6 text-center text-xs text-steam-muted">
                  Ничего не найдено
                </div>
              )}
            </div>
          )}

          {selectedProduct && (
            <div className="flex items-center gap-2 bg-steam-darker border border-steam-blue/40 rounded-steam px-3 py-2">
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-semibold text-steam-light">{selectedProduct.name}</p>
                {selectedProduct.best_offer && (
                  <p className="text-xs text-steam-green font-bold">{formatPrice(selectedProduct.best_offer.price)}</p>
                )}
              </div>
            </div>
          )}

          <div>
            <label className="text-[10px] uppercase tracking-wider text-steam-muted">Количество</label>
            <Input
              type="number"
              min="1"
              value={quantity}
              onChange={e => setQuantity(e.target.value)}
              className="mt-1"
            />
          </div>

          <div>
            <label className="text-[10px] uppercase tracking-wider text-steam-muted">Заметка</label>
            <textarea
              value={note}
              onChange={e => setNote(e.target.value)}
              className="mt-1 w-full rounded-steam border border-steam-border bg-steam-darker px-3 py-2 text-sm text-steam-light placeholder-steam-muted focus:border-steam-blue focus:outline-none"
              rows={2}
              placeholder="Например, нужна версия 16 ГБ..."
            />
          </div>

          <Button
            variant="green"
            className="w-full"
            disabled={!selectedProduct || !quantity || parseInt(quantity) < 1}
            loading={addItemMutation.isPending}
            onClick={() => addItemMutation.mutate()}
          >
            <Plus size={14} /> Добавить в вишлист
          </Button>
        </div>
      </Modal>
    </>
  )
}
