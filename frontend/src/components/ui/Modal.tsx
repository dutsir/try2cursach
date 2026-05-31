import * as Dialog from '@radix-ui/react-dialog'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}

export function Modal({ open, onClose, title, children }: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={v => !v && onClose()}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div
                className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              />
            </Dialog.Overlay>

            <Dialog.Content asChild>
              <motion.div
                className="fixed inset-0 z-50 flex items-center justify-center p-4"
                initial={{ opacity: 0, scale: 0.95, y: 16 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 16 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
              >
                <div className="w-full max-w-lg rounded-scout-lg border border-scout-border bg-scout-elevated shadow-2xl">
                  <div className="flex items-center justify-between border-b border-scout-subtle px-6 py-4">
                    <Dialog.Title className="text-base font-semibold text-scout-text">
                      {title}
                    </Dialog.Title>
                    <Dialog.Close asChild>
                      <button
                        className="rounded-scout p-1.5 text-scout-dim transition-colors hover:bg-scout-subtle hover:text-scout-text"
                        aria-label="Закрыть"
                      >
                        <X size={18} />
                      </button>
                    </Dialog.Close>
                  </div>
                  <div className="p-6">{children}</div>
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  )
}
