import { GitCompare } from 'lucide-react'
import { useCompareStore, type CompareCategory } from '@/store/compare'
import { useToast } from '@/components/ui/Toast'
import { cn } from '@/lib/utils'

interface Props {
  productId: number
  category: CompareCategory
  className?: string
}

export function CompareCheckbox({ productId, category, className }: Props) {
  const isSelected = useCompareStore(s => s.ids.includes(productId))
  const lockedCategoryId = useCompareStore(s => s.categoryId)
  const toggle = useCompareStore(s => s.toggle)
  const { toast } = useToast()

  // Список «привязан» к другой категории и этот товар туда не входит.
  const blocked = !isSelected && lockedCategoryId !== null && lockedCategoryId !== category.id

  const onClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const res = toggle(productId, category)
    if (!res.ok && res.reason) {
      toast(res.reason, 'error')
    }
  }

  return (
    <button
      onClick={onClick}
      title={
        blocked
          ? 'Другая категория — нельзя добавить к текущему сравнению'
          : isSelected
            ? 'Убрать из сравнения'
            : 'Добавить к сравнению'
      }
      className={cn(
        'p-1.5 rounded-scout transition-colors hover:bg-scout-subtle',
        isSelected ? 'text-scout-accent' : 'text-scout-dim',
        blocked && 'opacity-40',
        className,
      )}
    >
      <GitCompare size={14} className={isSelected ? 'fill-scout-accent/30' : ''} />
    </button>
  )
}
