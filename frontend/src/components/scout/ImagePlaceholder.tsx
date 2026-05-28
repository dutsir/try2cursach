interface ImagePlaceholderProps {
  width: number | string
  height: number
  label?: string
  src?: string | null
  className?: string
}

export function ImagePlaceholder({
  width,
  height,
  label = 'product shot',
  src,
  className,
}: ImagePlaceholderProps) {
  if (src) {
    return (
      <img
        src={src}
        alt={label}
        className={`object-cover rounded-scout ${className ?? ''}`}
        style={{ width, height }}
      />
    )
  }

  return (
    <div
      className={`flex items-center justify-center rounded-scout font-mono text-[11px] text-scout-dim tracking-[0.04em] ${className ?? ''}`}
      style={{
        width,
        height,
        background:
          'repeating-linear-gradient(135deg, #1C1C1C 0 8px, #141414 8px 16px)',
      }}
    >
      {label}
    </div>
  )
}
