import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { User, Mail, Lock, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/components/ui/Toast'
import { api, ApiError } from '@/api/client'
import type { User as UserType } from '@/types'

interface RegisterProps {
  onRegister?: (user: UserType) => void
}

export default function Register({ onRegister }: RegisterProps) {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    password_confirm: '',
  })
  const [acceptedTerms, setAcceptedTerms] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const { toast } = useToast()

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value,
    }))
    setError(null)
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    if (formData.password !== formData.password_confirm) {
      setError('Пароли не совпадают')
      setLoading(false)
      return
    }

    if (!acceptedTerms) {
      setError('Необходимо принять условия использования')
      setLoading(false)
      return
    }

    try {
      const user = await api.post<UserType>('/api/auth/register/', {
        ...formData,
        accepted_terms: acceptedTerms,
      })
      toast('Регистрация успешна', 'success')
      onRegister?.(user)
      setTimeout(() => navigate('/'), 300)
    } catch (e) {
      if (e instanceof ApiError) {
        try {
          const errors = JSON.parse(e.body)
          const firstError = Object.values(errors).flat()[0] as string
          setError(firstError || 'Ошибка регистрации')
        } catch {
          setError(e.body || 'Ошибка регистрации')
        }
      } else {
        setError('Ошибка при регистрации')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-scout-bg px-4 py-12">
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
        <div className="mb-8">
          <div className="scout-caption mb-3">scout</div>
          <h1 className="font-display text-[44px] font-bold lowercase leading-[0.95] tracking-[-0.03em] text-scout-text">
            create account.
          </h1>
          <p className="mt-3 text-sm text-scout-muted">
            один дашборд. один вердикт. начни отслеживать цены.
          </p>
        </div>

        <div className="rounded-scout-lg border border-scout-subtle bg-scout-elevated">
          <form onSubmit={handleRegister} className="flex flex-col gap-4 p-7">
            {error && (
              <div className="flex items-center gap-2 rounded-scout border border-scout-danger/30 bg-scout-danger/10 px-3 py-2 text-sm text-scout-danger">
                <AlertCircle size={14} className="flex-shrink-0" />
                {error}
              </div>
            )}

            <div>
              <label className="scout-caption mb-2 block">логин</label>
              <Input
                icon={<User size={15} />}
                type="text"
                name="username"
                placeholder="username"
                value={formData.username}
                onChange={handleChange}
                required
              />
            </div>

            <div>
              <label className="scout-caption mb-2 block">email</label>
              <Input
                icon={<Mail size={15} />}
                type="email"
                name="email"
                placeholder="your@email.com"
                value={formData.email}
                onChange={handleChange}
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="scout-caption mb-2 block">имя</label>
                <Input
                  type="text"
                  name="first_name"
                  placeholder="Иван"
                  value={formData.first_name}
                  onChange={handleChange}
                />
              </div>
              <div>
                <label className="scout-caption mb-2 block">фамилия</label>
                <Input
                  type="text"
                  name="last_name"
                  placeholder="Петров"
                  value={formData.last_name}
                  onChange={handleChange}
                />
              </div>
            </div>

            <div>
              <label className="scout-caption mb-2 block">пароль</label>
              <Input
                icon={<Lock size={15} />}
                type="password"
                name="password"
                placeholder="минимум 8 символов"
                value={formData.password}
                onChange={handleChange}
                minLength={8}
                required
              />
            </div>

            <div>
              <label className="scout-caption mb-2 block">подтвердите пароль</label>
              <Input
                icon={<Lock size={15} />}
                type="password"
                name="password_confirm"
                placeholder="повторите пароль"
                value={formData.password_confirm}
                onChange={handleChange}
                minLength={8}
                required
              />
            </div>

            <label className="flex cursor-pointer items-start gap-2.5 text-sm text-scout-muted">
              <input
                type="checkbox"
                checked={acceptedTerms}
                onChange={e => { setAcceptedTerms(e.target.checked); setError(null) }}
                className="mt-0.5 h-4 w-4 flex-shrink-0 cursor-pointer accent-scout-accent"
                required
              />
              <span>
                я принимаю условия использования и даю согласие на обработку данных.
                дублирование уведомлений о ценах в Telegram можно подключить в настройках.
              </span>
            </label>

            <Button type="submit" loading={loading} className="mt-2 w-full">
              зарегистрироваться
            </Button>
          </form>

          <div className="border-t border-scout-subtle px-7 py-4">
            <p className="text-center text-sm text-scout-muted">
              уже есть аккаунт?{' '}
              <Link to="/login" className="font-medium text-scout-accent transition-colors hover:text-scout-accent-hover">
                войти
              </Link>
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
