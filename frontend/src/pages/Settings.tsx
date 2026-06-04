import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Settings as SettingsIcon, Send, Link2, Unlink, Copy, Check, Mail, RefreshCw, CheckCircle, KeyRound, AtSign } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/components/ui/Toast'
import { accountApi, type TelegramLinkInfo, type TelegramStatus } from '@/api/account'
import { ApiError, parseApiError } from '@/api/client'
import type { User } from '@/types'

interface SettingsProps {
  user: User | null
  onUserChange: (user: User) => void
}

export default function Settings({ user, onUserChange }: SettingsProps) {
  const { toast } = useToast()
  const qc = useQueryClient()

  const [firstName, setFirstName] = useState(user?.first_name ?? '')
  const [lastName, setLastName] = useState(user?.last_name ?? '')
  const [savingProfile, setSavingProfile] = useState(false)

  const resendVerify = useMutation({
    mutationFn: () => accountApi.resendVerification(),
    onSuccess: () => toast('Письмо отправлено — проверьте почту', 'success'),
    onError: (err: unknown) => toast(parseApiError(err, 'Не удалось отправить письмо'), 'error'),
  })

  const toggleNotifyEmail = async (value: boolean) => {
    try {
      const updated = await accountApi.updateProfile({ notify_email: value })
      onUserChange(updated)
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch {
      toast('Не удалось изменить настройку', 'error')
    }
  }

  // Смена пароля
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('')
  const [changingPassword, setChangingPassword] = useState(false)

  // Смена email
  const [newEmail, setNewEmail] = useState('')
  const [emailPassword, setEmailPassword] = useState('')
  const [changingEmail, setChangingEmail] = useState(false)

  const [tg, setTg] = useState<TelegramStatus | null>(null)
  const [linkInfo, setLinkInfo] = useState<TelegramLinkInfo | null>(null)
  const [tgLoading, setTgLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const changePassword = async () => {
    if (newPassword.length < 8) {
      toast('Новый пароль должен быть не короче 8 символов', 'error')
      return
    }
    if (newPassword !== newPasswordConfirm) {
      toast('Пароли не совпадают', 'error')
      return
    }
    setChangingPassword(true)
    try {
      const res = await accountApi.changePassword(currentPassword, newPassword, newPasswordConfirm)
      toast(res.message ?? 'Пароль изменён', 'success')
      setCurrentPassword('')
      setNewPassword('')
      setNewPasswordConfirm('')
    } catch (e) {
      toast(parseApiError(e, 'Не удалось изменить пароль'), 'error')
    } finally {
      setChangingPassword(false)
    }
  }

  const changeEmail = async () => {
    if (!newEmail.includes('@')) {
      toast('Введите корректный email', 'error')
      return
    }
    setChangingEmail(true)
    try {
      const updated = await accountApi.changeEmail(newEmail, emailPassword)
      onUserChange(updated)
      qc.invalidateQueries({ queryKey: ['me'] })
      toast('Email изменён — проверьте новую почту для подтверждения', 'success')
      setNewEmail('')
      setEmailPassword('')
    } catch (e) {
      toast(parseApiError(e, 'Не удалось изменить email'), 'error')
    } finally {
      setChangingEmail(false)
    }
  }

  useEffect(() => {
    accountApi.telegramStatus().then(setTg).catch(() => {})
  }, [])

  const saveProfile = async () => {
    setSavingProfile(true)
    try {
      const updated = await accountApi.updateProfile({ first_name: firstName, last_name: lastName })
      onUserChange(updated)
      toast('Профиль сохранён', 'success')
    } catch {
      toast('Не удалось сохранить профиль', 'error')
    } finally {
      setSavingProfile(false)
    }
  }

  const toggleNotifyTelegram = async (value: boolean) => {
    try {
      const updated = await accountApi.updateProfile({ notify_telegram: value })
      onUserChange(updated)
      setTg(prev => (prev ? { ...prev, notify_telegram: value } : prev))
    } catch {
      toast('Не удалось изменить настройку', 'error')
    }
  }

  const startLink = async () => {
    setTgLoading(true)
    try {
      const info = await accountApi.telegramLink()
      setLinkInfo(info)
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) {
        toast('Telegram-интеграция отключена на сервере', 'error')
      } else {
        toast('Не удалось получить код привязки', 'error')
      }
    } finally {
      setTgLoading(false)
    }
  }

  const refreshStatus = async () => {
    const status = await accountApi.telegramStatus().catch(() => null)
    if (status) {
      setTg(status)
      if (status.linked) {
        setLinkInfo(null)
        toast('Telegram привязан', 'success')
      } else {
        toast('Пока не вижу привязки. Отправьте боту код и попробуйте снова.', 'info')
      }
    }
  }

  const unlink = async () => {
    setTgLoading(true)
    try {
      await accountApi.telegramUnlink()
      setTg({ linked: false, telegram_username: '', notify_telegram: false })
      setLinkInfo(null)
      if (user) onUserChange({ ...user, telegram_linked: false, telegram_username: '', notify_telegram: false })
      toast('Telegram отвязан', 'success')
    } catch {
      toast('Не удалось отвязать Telegram', 'error')
    } finally {
      setTgLoading(false)
    }
  }

  const copyCode = () => {
    if (!linkInfo) return
    navigator.clipboard.writeText(`/start ${linkInfo.code}`).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <>
      <motion.div
        className="mb-8 flex items-center gap-3"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <SettingsIcon size={28} className="text-scout-accent" />
        <div>
          <h1 className="text-3xl font-bold text-scout-text">Настройки</h1>
          <p className="text-sm text-scout-muted">Профиль и уведомления</p>
        </div>
      </motion.div>

      <div className="flex max-w-2xl flex-col gap-6">
        {/* Профиль */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-scout-text">Аккаунт</h2>
          <div className="mt-4 flex flex-col gap-4">
            <div>
              <label className="scout-caption mb-2 block">email</label>
              <Input type="email" value={user?.email ?? ''} disabled />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="scout-caption mb-2 block">имя</label>
                <Input value={firstName} onChange={e => setFirstName(e.target.value)} placeholder="Иван" />
              </div>
              <div>
                <label className="scout-caption mb-2 block">фамилия</label>
                <Input value={lastName} onChange={e => setLastName(e.target.value)} placeholder="Петров" />
              </div>
            </div>
            <div>
              <Button onClick={saveProfile} loading={savingProfile}>Сохранить</Button>
            </div>
          </div>
        </Card>

        {/* Смена пароля */}
        <Card className="p-6">
          <div className="flex items-center gap-2">
            <KeyRound size={18} className="text-scout-accent" />
            <h2 className="text-lg font-semibold text-scout-text">Сменить пароль</h2>
          </div>
          <div className="mt-4 flex flex-col gap-4">
            <div>
              <label className="scout-caption mb-2 block">текущий пароль</label>
              <Input
                type="password"
                value={currentPassword}
                onChange={e => setCurrentPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="scout-caption mb-2 block">новый пароль</label>
                <Input
                  type="password"
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  placeholder="не менее 8 символов"
                  autoComplete="new-password"
                />
              </div>
              <div>
                <label className="scout-caption mb-2 block">повторите пароль</label>
                <Input
                  type="password"
                  value={newPasswordConfirm}
                  onChange={e => setNewPasswordConfirm(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="new-password"
                />
              </div>
            </div>
            <div>
              <Button
                onClick={changePassword}
                loading={changingPassword}
                disabled={!currentPassword || !newPassword || !newPasswordConfirm}
              >
                Изменить пароль
              </Button>
            </div>
          </div>
        </Card>

        {/* Смена email */}
        <Card className="p-6">
          <div className="flex items-center gap-2">
            <AtSign size={18} className="text-scout-accent" />
            <h2 className="text-lg font-semibold text-scout-text">Сменить email</h2>
          </div>
          <p className="mt-1 text-sm text-scout-muted">
            После смены потребуется подтвердить новую почту по ссылке из письма.
          </p>
          <div className="mt-4 flex flex-col gap-4">
            <div>
              <label className="scout-caption mb-2 block">новый email</label>
              <Input
                type="email"
                value={newEmail}
                onChange={e => setNewEmail(e.target.value)}
                placeholder="new@example.com"
                autoComplete="email"
              />
            </div>
            <div>
              <label className="scout-caption mb-2 block">текущий пароль</label>
              <Input
                type="password"
                value={emailPassword}
                onChange={e => setEmailPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>
            <div>
              <Button
                onClick={changeEmail}
                loading={changingEmail}
                disabled={!newEmail || !emailPassword}
              >
                Изменить email
              </Button>
            </div>
          </div>
        </Card>

        {/* Email */}
        <Card className="p-6">
          <div className="flex items-center gap-2">
            <Mail size={18} className="text-scout-accent" />
            <h2 className="text-lg font-semibold text-scout-text">Email-уведомления</h2>
          </div>
          <p className="mt-1 text-sm text-scout-muted">
            Дублирование уведомлений о ценах на почту.
          </p>

          <div className="mt-4 flex flex-col gap-4">
            {/* Статус верификации */}
            {user?.email_verified ? (
              <div className="flex items-center gap-2 rounded-scout border border-scout-success/30 bg-scout-success/10 px-3 py-2 text-sm text-scout-success">
                <CheckCircle size={15} />
                Почта подтверждена: {user.email}
              </div>
            ) : (
              <div className="flex flex-col gap-2 rounded-scout border border-scout-warning/30 bg-scout-warning/10 px-3 py-2">
                <p className="text-sm text-scout-warning">
                  Почта не подтверждена — уведомления не придут.
                </p>
                <Button
                  variant="secondary"
                  onClick={() => resendVerify.mutate()}
                  loading={resendVerify.isPending}
                  className="w-fit"
                >
                  <RefreshCw size={14} className="mr-1.5" />
                  Отправить письмо снова
                </Button>
              </div>
            )}

            {/* Тоггл уведомлений */}
            <label className="flex cursor-pointer items-center justify-between">
              <span className="text-sm text-scout-text">Присылать уведомления на email</span>
              <input
                type="checkbox"
                checked={user?.notify_email ?? true}
                onChange={e => toggleNotifyEmail(e.target.checked)}
                className="h-4 w-4 cursor-pointer accent-scout-accent"
              />
            </label>
          </div>
        </Card>

        {/* Telegram */}
        <Card className="p-6">
          <div className="flex items-center gap-2">
            <Send size={18} className="text-scout-accent" />
            <h2 className="text-lg font-semibold text-scout-text">Telegram</h2>
          </div>
          <p className="mt-1 text-sm text-scout-muted">
            Дублирование уведомлений о ценах в Telegram.
          </p>

          {tg?.linked ? (
            <div className="mt-4 flex flex-col gap-4">
              <div className="flex items-center gap-2 rounded-scout border border-scout-success/30 bg-scout-success/10 px-3 py-2 text-sm text-scout-success">
                <Check size={15} />
                Привязан{tg.telegram_username ? `: @${tg.telegram_username}` : ''}
              </div>

              <label className="flex cursor-pointer items-center justify-between">
                <span className="text-sm text-scout-text">Присылать уведомления в Telegram</span>
                <input
                  type="checkbox"
                  checked={tg.notify_telegram}
                  onChange={e => toggleNotifyTelegram(e.target.checked)}
                  className="h-4 w-4 cursor-pointer accent-scout-accent"
                />
              </label>

              <div>
                <Button variant="danger" onClick={unlink} loading={tgLoading}>
                  <Unlink size={15} className="mr-1.5" />
                  Отвязать
                </Button>
              </div>
            </div>
          ) : (
            <div className="mt-4 flex flex-col gap-4">
              {!linkInfo ? (
                <div>
                  <Button onClick={startLink} loading={tgLoading}>
                    <Link2 size={15} className="mr-1.5" />
                    Подключить Telegram
                  </Button>
                </div>
              ) : (
                <div className="flex flex-col gap-3 rounded-scout border border-scout-subtle bg-scout-bg p-4">
                  <p className="text-sm text-scout-text">{linkInfo.instructions}</p>

                  <div className="flex items-center gap-2">
                    <code className="flex-1 rounded-scout border border-scout-subtle bg-scout-elevated px-3 py-2 text-sm text-scout-accent">
                      /start {linkInfo.code}
                    </code>
                    <button
                      onClick={copyCode}
                      className="rounded-scout border border-scout-subtle p-2 text-scout-muted transition-colors hover:text-scout-text"
                      title="Скопировать"
                    >
                      {copied ? <Check size={16} className="text-scout-success" /> : <Copy size={16} />}
                    </button>
                  </div>

                  {linkInfo.deep_link && (
                    <a
                      href={linkInfo.deep_link}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm text-scout-accent transition-colors hover:text-scout-accent-hover"
                    >
                      Открыть бота в Telegram →
                    </a>
                  )}

                  <p className="text-xs text-scout-dim">
                    Код действует {linkInfo.expires_in_minutes} мин. После отправки кода боту нажмите «Проверить».
                  </p>

                  <div>
                    <Button variant="secondary" onClick={refreshStatus}>Проверить привязку</Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </>
  )
}
