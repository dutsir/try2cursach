export function fmt(n: number): string {
  return n.toLocaleString('ru-RU')
}

export function genSeries(n: number, start: number, end: number, jitter = 0.04): number[] {
  const out: number[] = []
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1)
    const base = start + (end - start) * t
    const noise = (Math.sin(i * 1.7) + Math.sin(i * 0.43) * 0.6) * (start * jitter)
    out.push(Math.round(base + noise))
  }
  return out
}

export function computeTrend(current: number, prev: number) {
  const trend = ((current - prev) / prev) * 100
  const up = trend > 0
  return {
    percent: trend,
    abs: Math.abs(trend),
    diff: Math.abs(current - prev),
    up,
    color: up ? '#EF4444' : '#10B981',
    arrow: up ? '↑' : '↓',
  }
}
