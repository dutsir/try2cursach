import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mail, CheckCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { accountApi } from '@/api/account'
import { ApiError } from '@/api/client'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await accountApi.requestPasswordReset(email)
      setSent(true)
    } catch (e) {
      if (e instanceof ApiError) {
        try {
          setError(JSON.parse(e.body).error || 'Не удалось отправить письмо.')
        } catch {
          setError('Не удалось отправить письмо.')
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
            forgot password?
          </h1>
          <p className="mt-3 text-sm text-scout-muted">
            введи email — пришлём ссылку для сброса пароля.
          </p>
        </div>

        <div className="rounded-scout-lg border border-scout-subtle bg-scout-elevated">
          {sent ? (
            <div className="p-7 text-center">
              <CheckCircle size={44} className="mx-auto mb-4 text-scout-success" />
              <h2 className="mb-2 text-lg font-bold text-scout-text">Проверьте почту</h2>
              <p className="text-sm text-scout-muted">
                Если такой email зарегистрирован, мы отправили ссылку для сброса. Ссылка действительна 3 дня.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-5 p-7">
              <div>
                <label className="scout-caption mb-2 block">email</label>
                <Input
                  icon={<Mail size={15} />}
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                />
              </div>
              {error && <p className="text-sm text-scout-danger">{error}</p>}
              <Button type="submit" loading={loading} className="mt-1 w-full">
                отправить ссылку
              </Button>
            </form>
          )}

          <div className="border-t border-scout-subtle px-7 py-4">
            <p className="text-center text-sm text-scout-muted">
              вспомнили пароль?{' '}
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
