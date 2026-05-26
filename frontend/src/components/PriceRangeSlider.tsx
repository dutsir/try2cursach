import * as RSlider from '@radix-ui/react-slider'
import { useEffect, useState } from 'react'
import { useDebounce } from '@/hooks/useDebounce'

interface Props {
  min: number
  max: number
  value: [number | null, number | null]
  onChange: (range: [number | null, number | null]) => void
}

/**
 * Two-thumb slider диапазона цен с debounce 500ms на изменение.
 * Текущие значения показываются над ползунками; пользователь также
 * может ввести вручную в input.
 */
export function PriceRangeSlider({ min, max, value, onChange }: Props) {
  const [low, setLow] = useState(value[0] ?? min)
  const [high, setHigh] = useState(value[1] ?? max)
  const debouncedLow = useDebounce(low, 500)
  const debouncedHigh = useDebounce(high, 500)

  useEffect(() => {
    setLow(value[0] ?? min)
    setHigh(value[1] ?? max)
  }, [value, min, max])

  useEffect(() => {
    const nextLow = debouncedLow > min ? debouncedLow : null
    const nextHigh = debouncedHigh < max ? debouncedHigh : null
    if (nextLow !== value[0] || nextHigh !== value[1]) {
      onChange([nextLow, nextHigh])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedLow, debouncedHigh])

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={low}
          min={min}
          max={high}
          onChange={e => setLow(Math.max(min, Math.min(Number(e.target.value), high)))}
          className="w-full rounded-steam border border-steam-border bg-steam-darker px-2 py-1.5 text-xs text-steam-light focus:border-steam-blue focus:outline-none"
        />
        <span className="text-steam-muted">—</span>
        <input
          type="number"
          value={high}
          min={low}
          max={max}
          onChange={e => setHigh(Math.min(max, Math.max(Number(e.target.value), low)))}
          className="w-full rounded-steam border border-steam-border bg-steam-darker px-2 py-1.5 text-xs text-steam-light focus:border-steam-blue focus:outline-none"
        />
      </div>

      <RSlider.Root
        className="relative flex h-5 w-full touch-none select-none items-center"
        min={min}
        max={max}
        step={Math.max(1, Math.round((max - min) / 1000))}
        value={[low, high]}
        onValueChange={([a, b]) => { setLow(a); setHigh(b) }}
        minStepsBetweenThumbs={1}
      >
        <RSlider.Track className="relative h-1 grow rounded-full bg-steam-border">
          <RSlider.Range className="absolute h-full rounded-full bg-steam-blue" />
        </RSlider.Track>
        <RSlider.Thumb
          aria-label="Минимальная цена"
          className="block h-4 w-4 rounded-full bg-steam-blue shadow ring-1 ring-steam-darker hover:scale-110 transition-transform"
        />
        <RSlider.Thumb
          aria-label="Максимальная цена"
          className="block h-4 w-4 rounded-full bg-steam-blue shadow ring-1 ring-steam-darker hover:scale-110 transition-transform"
        />
      </RSlider.Root>

      <div className="flex justify-between text-[10px] text-steam-muted">
        <span>{min.toLocaleString('ru-RU')} ₽</span>
        <span>{max.toLocaleString('ru-RU')} ₽</span>
      </div>
    </div>
  )
}
