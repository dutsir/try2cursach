import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { dashboardApi } from '@/api/dashboard'
import { useAuth } from '@/hooks/useAuth'
import { DashStats } from '@/components/scout'

function formatToday(): string {
  const d = new Date()
  const days = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота']
  const months = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
  ]
  const day = days[d.getDay()]
  const date = d.getDate()
  const month = months[d.getMonth()]
  const hours = d.getHours().toString().padStart(2, '0')
  const minutes = d.getMinutes().toString().padStart(2, '0')
  return `${day} · ${date} ${month}, ${hours}:${minutes}`
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [query, setQuery] = useState('')

  const { data: dash } = useQuery({
    queryKey: ['dashboard'],
    queryFn: dashboardApi.get,
    staleTime: 5 * 60_000,
  })

  const totalTracked = dash?.totals?.products ?? 0
  const priceRecords = dash?.totals?.price_records ?? 0
  const greetingName = (user?.first_name || user?.username || '').toLowerCase()
  const greeting = greetingName ? `добрый день, ${greetingName}.` : 'добрый день.'

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    const q = query.trim()
    navigate(q ? `/catalog?search=${encodeURIComponent(q)}` : '/catalog')
  }

  return (
    <div className="animate-scout-rise mx-auto flex min-h-[68vh] max-w-3xl flex-col items-center justify-center py-10 text-center">
      <div className="scout-caption">{formatToday()}</div>
      <h1 className="mt-3 font-display text-[44px] font-bold lowercase tracking-[-0.02em] text-scout-text md:text-[56px]">
        {greeting}
      </h1>
      <p className="mt-3 text-base text-scout-muted">
        лучшие скидки и реальные минимумы цен — без догадок.
      </p>

      <form onSubmit={handleSearch} className="mt-10 w-full">
        <div className="group flex items-center gap-3 rounded-scout-lg border border-scout-subtle bg-scout-elevated px-5 h-16 transition-all focus-within:border-scout-accent/60 focus-within:shadow-[0_0_0_4px_rgba(168,85,247,0.12)]">
          <Search
            size={22}
            className="shrink-0 text-scout-dim transition-colors group-focus-within:text-scout-accent"
          />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoFocus
            placeholder="Поиск по товарам, маркетплейсам…"
            className="flex-1 border-none bg-transparent text-[18px] text-scout-text outline-none placeholder:text-scout-dim"
          />
          <button type="submit" className="scout-btn-primary shrink-0 text-[14px]">
            найти
          </button>
        </div>
      </form>

      <div className="mt-10 w-full">
        <DashStats tracked={totalTracked} priceRecords={priceRecords} />
      </div>
    </div>
  )
}
