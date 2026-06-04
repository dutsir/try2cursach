import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Mail, X, RefreshCw } from 'lucide-react'
import { accountApi } from '@/api/account'
import { parseApiError } from '@/api/client'
import { useToast } from '@/components/ui/Toast'
import type { User } from '@/types'

interface Props {
  user: User
}

export function EmailVerifyBanner({ user }: Props) {
  const [dismissed, setDismissed] = useState(false)
  const qc = useQueryClient()
  const { toast } = useToast()

  const resend = useMutation({
    mutationFn: () => accountApi.resendVerification(),
    onSuccess: () => {
      toast('Письмо отправлено — проверьте почту', 'success')
      qc.invalidateQueries({ queryKey: ['me'] })
    },
    onError: (err: unknown) => {
      toast(parseApiError(err, 'Не удалось отправить письмо'), 'error')
    },
  })

  if (user.email_verified || dismissed) return null

  return (
    <div className="bg-scout-warning/10 border-b border-scout-warning/30 px-4 py-2.5">
      <div className="max-w-6xl mx-auto flex items-center gap-3">
        <Mail size={15} className="text-scout-warning shrink-0" />
        <p className="flex-1 text-sm text-scout-warning">
          Подтвердите email <span className="font-medium">{user.email}</span> — без этого уведомления на почту не придут.
        </p>
        <button
          onClick={() => resend.mutate()}
          disabled={resend.isPending}
          className="flex items-center gap-1.5 text-xs font-medium text-scout-warning hover:text-scout-text transition-colors shrink-0"
        >
          <RefreshCw size={12} className={resend.isPending ? 'animate-spin' : ''} />
          {resend.isPending ? 'Отправляем…' : 'Отправить снова'}
        </button>
        <button
          onClick={() => setDismissed(true)}
          className="text-scout-dim hover:text-scout-text transition-colors shrink-0"
          aria-label="Закрыть"
        >
          <X size={15} />
        </button>
      </div>
    </div>
  )
}
