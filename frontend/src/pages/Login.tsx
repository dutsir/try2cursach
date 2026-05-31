import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mail, Lock, Eye, EyeOff } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/components/ui/Toast'
import { api, ApiError } from '@/api/client'
import type { User } from '@/types'

interface LoginProps {
  onLogin?: (user: User) => void
}

export default function Login({ onLogin }: LoginProps) {
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
      const user = await api.post<User>('/api/auth/login/', { username, password })
      onLogin?.(user)
      toast('Вы вошли в систему', 'success')
      setTimeout(() => navigate('/'), 300)
    } catch (e) {
      if (e instanceof ApiError) {
        try {
          const err = JSON.parse(e.body)
          toast(err.error || 'Неверный логин или пароль', 'error')
        } catch {
          toast('Неверный логин или пароль', 'error')
        }
      } else {
        toast('Ошибка при входе', 'error')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-scout-bg px-4">
      {/* Ambient accent glow — quiet, single accent */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute -top-40 left-1/4 h-96 w-96 rounded-full bg-scout-accent/10 blur-[140px]" />
        <div className="absolute bottom-0 right-1/4 h-96 w-96 rounded-full bg-scout-accent/5 blur-[140px]" />
      </div>

      <motion.div
        className="relative w-full max-w-md"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        {/* Header */}
        <div className="mb-8">
          <div className="scout-caption mb-3">scout</div>
          <h1 className="font-display text-[44px] font-bold lowercase leading-[0.95] tracking-[-0.03em] text-scout-text">
            welcome back.
          </h1>
          <p className="mt-3 text-sm text-scout-muted">
            войди, чтобы продолжить следить за ценами.
          </p>
        </div>

        {/* Card */}
        <div className="rounded-scout-lg border border-scout-subtle bg-scout-elevated">
          <form onSubmit={handleLogin} className="flex flex-col gap-5 p-7">
            <div>
              <label className="scout-caption mb-2 block">логин или email</label>
              <Input
                icon={<Mail size={15} />}
                type="text"
                placeholder="username"
                value={username}
                onChange={e => setUsername(e.target.value)}
              />
            </div>

            <div>
              <label className="scout-caption mb-2 block">пароль</label>
              <div className="relative">
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
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-scout-dim transition-colors hover:text-scout-text"
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <Button type="submit" loading={loading} className="mt-1 w-full">
              войти
            </Button>
          </form>

          <div className="border-t border-scout-subtle px-7 py-4">
            <p className="text-center text-sm text-scout-muted">
              нет аккаунта?{' '}
              <Link to="/register" className="font-medium text-scout-accent transition-colors hover:text-scout-accent-hover">
                зарегистрироваться
              </Link>
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
