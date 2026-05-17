import * as ToastPrimitive from '@radix-ui/react-toast'
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, AlertCircle, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type ToastType = 'success' | 'error' | 'info'

interface ToastItem {
  id: string
  type: ToastType
  message: string
}

interface ToastCtx {
  toast: (message: string, type?: ToastType) => void
}

const Ctx = createContext<ToastCtx>({ toast: () => {} })

export function useToast() {
  return useContext(Ctx)
}

const icons: Record<ToastType, ReactNode> = {
  success: <CheckCircle size={16} className="text-emerald-400" />,
  error:   <AlertCircle size={16} className="text-red-400" />,
  info:    <AlertCircle size={16} className="text-sky-400" />,
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const toast = useCallback((message: string, type: ToastType = 'info') => {
    const id = Math.random().toString(36).slice(2)
    setToasts(t => [...t, { id, type, message }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000)
  }, [])

  return (
    <Ctx.Provider value={{ toast }}>
      <ToastPrimitive.Provider>
        {children}
        <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2" />
        <AnimatePresence>
          {toasts.map(t => (
            <ToastPrimitive.Root key={t.id} asChild open>
              <motion.div
                initial={{ opacity: 0, x: 48 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 48 }}
                className={cn(
                  'flex items-center gap-3 rounded-xl border border-white/15 bg-slate-800/90 px-4 py-3 shadow-xl backdrop-blur-xl',
                  'text-sm text-white',
                )}
              >
                {icons[t.type]}
                <span className="flex-1">{t.message}</span>
                <button
                  onClick={() => setToasts(s => s.filter(x => x.id !== t.id))}
                  className="text-white/40 hover:text-white"
                >
                  <X size={14} />
                </button>
              </motion.div>
            </ToastPrimitive.Root>
          ))}
        </AnimatePresence>
      </ToastPrimitive.Provider>
    </Ctx.Provider>
  )
}
