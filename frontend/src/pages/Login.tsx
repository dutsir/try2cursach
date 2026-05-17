import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mail, Lock, Eye, EyeOff } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/components/ui/Toast'
import { formatPrice } from '@/lib/utils'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { toast } = useToast()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const res = await fetch('/api/auth/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ username, password }),
      })

      if (res.ok) {
        toast('Вы вошли в систему', 'success')
        setTimeout(() => navigate('/'), 500)
      } else {
        const err = await res.json()
        toast(err.error || 'Неверный логин или пароль', 'error')
      }
    } catch (e) {
      toast('Ошибка при входе', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900">
      {/* Ambient */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute -top-40 left-1/4 h-96 w-96 rounded-full bg-brand-600/20 blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 h-96 w-96 rounded-full bg-purple-600/15 blur-[120px]" />
      </div>

      <div className="relative flex min-h-screen items-center justify-center px-4">
        <motion.div
          className="w-full max-w-md"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          {/* Header */}
          <div className="mb-8 text-center">
            <div className="mb-4 flex justify-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-purple-600 font-bold text-white text-lg">
                P
              </span>
            </div>
            <h1 className="text-3xl font-bold text-white">PriceWatch</h1>
            <p className="mt-2 text-white/40">Мониторинг цен на технику</p>
          </div>

          {/* Card */}
          <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl shadow-xl">
            <form onSubmit={handleLogin} className="flex flex-col gap-4 p-8">
              <div className="mb-2">
                <label className="text-xs font-medium text-white/60">Логин или email</label>
                <Input
                  icon={<Mail size={15} />}
                  type="text"
                  placeholder="username"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  className="mt-1.5"
                />
              </div>

              <div className="mb-4">
                <label className="text-xs font-medium text-white/60">Пароль</label>
                <div className="relative mt-1.5">
                  <Input
                    icon={<Lock size={15} />}
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white transition"
                  >
                    {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              <Button type="submit" loading={loading} className="w-full">
                Войти
              </Button>
            </form>

            <div className="border-t border-white/10 px-8 py-4">
              <p className="text-center text-sm text-white/60">
                Нет аккаунта?{' '}
                <Link to="/register" className="font-medium text-brand-400 hover:text-brand-300 transition">
                  Зарегистрируйтесь
                </Link>
              </p>
            </div>
          </div>

          {/* Features */}
          <div className="mt-8 grid grid-cols-3 gap-4 text-center">
            {[
              { icon: '📊', label: 'Графики' },
              { icon: '🔔', label: 'Алерты' },
              { icon: '💰', label: 'Сравнение' },
            ].map(f => (
              <div key={f.label} className="text-white/40">
                <div className="text-2xl mb-1">{f.icon}</div>
                <p className="text-xs">{f.label}</p>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  )
}
