import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { CheckCircle, XCircle, Loader2 } from 'lucide-react'
import { accountApi } from '@/api/account'
import { Button } from '@/components/ui/Button'

type State = 'loading' | 'success' | 'error'

export default function VerifyEmail() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token') ?? ''
  const [state, setState] = useState<State>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!token) {
      setState('error')
      setMessage('Токен не найден в ссылке.')
      return
    }
    accountApi.verifyEmail(token)
      .then(res => {
        setState('success')
        setMessage(res.message ?? 'Email успешно подтверждён.')
      })
      .catch(err => {
        setState('error')
        setMessage(
          err?.response?.data?.error ??
          err?.message ??
          'Недействительная или устаревшая ссылка.'
        )
      })
  }, [token])

  return (
    <div className="min-h-screen bg-scout-bg flex items-center justify-center px-4">
      <motion.div
        className="w-full max-w-md bg-scout-elevated border border-scout-subtle rounded-scout-lg p-8 text-center"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        {state === 'loading' && (
          <>
            <Loader2 size={48} className="mx-auto text-scout-accent animate-spin mb-4" />
            <h1 className="text-xl font-bold text-scout-text">Проверяем ссылку…</h1>
          </>
        )}

        {state === 'success' && (
          <>
            <CheckCircle size={48} className="mx-auto text-scout-success mb-4" />
            <h1 className="text-xl font-bold text-scout-text mb-2">Email подтверждён!</h1>
            <p className="text-sm text-scout-muted mb-6">{message}</p>
            <Button className="w-full" onClick={() => navigate('/dashboard')}>
              Перейти в дашборд
            </Button>
          </>
        )}

        {state === 'error' && (
          <>
            <XCircle size={48} className="mx-auto text-scout-danger mb-4" />
            <h1 className="text-xl font-bold text-scout-text mb-2">Не удалось подтвердить</h1>
            <p className="text-sm text-scout-muted mb-6">{message}</p>
            <Button variant="secondary" className="w-full" onClick={() => navigate('/settings')}>
              Запросить новое письмо
            </Button>
          </>
        )}
      </motion.div>
    </div>
  )
}
