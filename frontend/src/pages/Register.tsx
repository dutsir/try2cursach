import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { User, Mail, Lock, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/components/ui/Toast'

export default function Register() {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    password_confirm: '',
  })
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

    try {
      const res = await fetch('/api/auth/register/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })

      if (res.ok) {
        toast('Регистрация успешна! Войдите в аккаунт', 'success')
        setTimeout(() => navigate('/login'), 500)
      } else {
        const err = await res.json()
        setError(Object.values(err).flat()[0] as string || 'Ошибка регистрации')
      }
    } catch (e) {
      setError('Ошибка при регистрации')
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

      <div className="relative flex min-h-screen items-center justify-center px-4 py-12">
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
            <h1 className="text-3xl font-bold text-white">Регистрация</h1>
            <p className="mt-2 text-white/40">Создайте аккаунт для начала работы</p>
          </div>

          {/* Card */}
          <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl shadow-xl">
            <form onSubmit={handleRegister} className="flex flex-col gap-3 p-8">
              {error && (
                <div className="mb-2 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
                  <AlertCircle size={14} />
                  {error}
                </div>
              )}

              <div>
                <label className="text-xs font-medium text-white/60">Логин</label>
                <Input
                  icon={<User size={15} />}
                  type="text"
                  name="username"
                  placeholder="username"
                  value={formData.username}
                  onChange={handleChange}
                  className="mt-1"
                  required
                />
              </div>

              <div>
                <label className="text-xs font-medium text-white/60">Email</label>
                <Input
                  icon={<Mail size={15} />}
                  type="email"
                  name="email"
                  placeholder="your@email.com"
                  value={formData.email}
                  onChange={handleChange}
                  className="mt-1"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs font-medium text-white/60">Имя</label>
                  <Input
                    type="text"
                    name="first_name"
                    placeholder="Иван"
                    value={formData.first_name}
                    onChange={handleChange}
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-white/60">Фамилия</label>
                  <Input
                    type="text"
                    name="last_name"
                    placeholder="Петров"
                    value={formData.last_name}
                    onChange={handleChange}
                    className="mt-1"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-white/60">Пароль</label>
                <Input
                  icon={<Lock size={15} />}
                  type="password"
                  name="password"
                  placeholder="Минимум 8 символов"
                  value={formData.password}
                  onChange={handleChange}
                  className="mt-1"
                  minLength={8}
                  required
                />
              </div>

              <div className="mb-2">
                <label className="text-xs font-medium text-white/60">Подтвердите пароль</label>
                <Input
                  icon={<Lock size={15} />}
                  type="password"
                  name="password_confirm"
                  placeholder="Повторите пароль"
                  value={formData.password_confirm}
                  onChange={handleChange}
                  className="mt-1"
                  minLength={8}
                  required
                />
              </div>

              <Button type="submit" loading={loading} className="w-full mt-2">
                Зарегистрироваться
              </Button>
            </form>

            <div className="border-t border-white/10 px-8 py-4">
              <p className="text-center text-sm text-white/60">
                Уже есть аккаунт?{' '}
                <Link to="/login" className="font-medium text-brand-400 hover:text-brand-300 transition">
                  Войти
                </Link>
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
