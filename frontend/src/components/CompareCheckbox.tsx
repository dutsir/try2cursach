import { GitCompare } from 'lucide-react'
import { useCompareStore } from '@/store/compare'
import { useToast } from '@/components/ui/Toast'
import { cn } from '@/lib/utils'

interface Props {
  productId: number
  className?: string
}

/**
 * Кнопка-чекбокс «В сравнение» для карточки товара.
 * При попытке добавить 5-й — toast «Максимум 4».
 */
export function CompareCheckbox({ productId, className }: Props) {
  const isSelected = useCompareStore(s => s.ids.includes(productId))
  const toggle = useCompareStore(s => s.toggle)
  const { toast } = useToast()

  const onClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const res = toggle(productId)
    if (!res.ok && res.reason) {
      toast(res.reason, 'error')
    }
  }

  return (
    <button
      onClick={onClick}
      title={isSelected ? 'Убрать из сравнения' : 'Добавить к сравнению'}
      className={cn(
        'p-1.5 rounded-steam transition-colors hover:bg-steam-panel',
        isSelected ? 'text-steam-blue' : 'text-steam-muted',
        className,
      )}
    >
      <GitCompare size={14} className={isSelected ? 'fill-steam-blue/30' : ''} />
    </button>
  )
}
