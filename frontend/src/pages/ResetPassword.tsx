import { useState } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Lock, Eye, EyeOff, CheckCircle, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { accountApi } from '@/api/account'
import { ApiError } from '@/api/client'

export default function ResetPassword() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const uid = params.get('uid') ?? ''
  const token = params.get('token') ?? ''

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [show, setShow] = useState(false)
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  const linkValid = Boolean(uid && token)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Пароль должен быть не короче 8 символов.')
      return
    }
    if (password !== confirm) {
      setError('Пароли не совпадают.')
      return
    }
    setLoading(true)
    try {
      await accountApi.confirmPasswordReset(uid, token, password, confirm)
      setDone(true)
      setTimeout(() => navigate('/login'), 1800)
    } catch (e) {
      if (e instanceof ApiError) {
        try {
          setError(JSON.parse(e.body).error || 'Не удалось изменить пароль.')
        } catch {
          setError('Не удалось изменить пароль.')
        }
      } else {
        setError('Ошибка сети.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-scout-bg px-4">
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
            new password.
          </h1>
          <p className="mt-3 text-sm text-scout-muted">задай новый пароль для входа.</p>
        </div>

        <div className="rounded-scout-lg border border-scout-subtle bg-scout-elevated">
          {!linkValid ? (
            <div className="p-7 text-center">
              <XCircle size={44} className="mx-auto mb-4 text-scout-danger" />
              <h2 className="mb-2 text-lg font-bold text-scout-text">Ссылка повреждена</h2>
              <p className="mb-6 text-sm text-scout-muted">
                В ссылке нет нужных параметров. Запросите сброс заново.
              </p>
              <Button variant="secondary" className="w-full" onClick={() => navigate('/forgot-password')}>
                Запросить сброс
              </Button>
            </div>
          ) : done ? (
            <div className="p-7 text-center">
              <CheckCircle size={44} className="mx-auto mb-4 text-scout-success" />
              <h2 className="mb-2 text-lg font-bold text-scout-text">Пароль изменён!</h2>
              <p className="text-sm text-scout-muted">Перенаправляем на страницу входа…</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-5 p-7">
              <div>
                <label className="scout-caption mb-2 block">новый пароль</label>
                <div className="relative">
                  <Input
                    icon={<Lock size={15} />}
                    type={show ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShow(!show)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-scout-dim transition-colors hover:text-scout-text"
                  >
                    {show ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>
              <div>
                <label className="scout-caption mb-2 block">повтор пароля</label>
                <Input
                  icon={<Lock size={15} />}
                  type={show ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={confirm}
                  onChange={e => setConfirm(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-scout-danger">{error}</p>}
              <Button type="submit" loading={loading} className="mt-1 w-full">
                сохранить пароль
              </Button>
            </form>
          )}

          <div className="border-t border-scout-subtle px-7 py-4">
            <p className="text-center text-sm text-scout-muted">
              <Link to="/login" className="font-medium text-scout-accent transition-colors hover:text-scout-accent-hover">
                вернуться ко входу
              </Link>
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
