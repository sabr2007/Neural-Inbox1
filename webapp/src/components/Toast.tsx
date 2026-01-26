import { createContext, useState, useCallback, useEffect, ReactNode } from 'react'
import { X } from 'lucide-react'

export type ToastType = 'success' | 'error'

interface Toast {
  id: number
  message: string
  type: ToastType
}

interface ToastContextValue {
  showSuccess: (message: string) => void
  showError: (message: string) => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)

let toastId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((message: string, type: ToastType) => {
    const id = ++toastId
    setToasts((prev) => [...prev, { id, message, type }])
  }, [])

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const showSuccess = useCallback((message: string) => addToast(message, 'success'), [addToast])
  const showError = useCallback((message: string) => addToast(message, 'error'), [addToast])

  return (
    <ToastContext.Provider value={{ showSuccess, showError }}>
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  )
}

function ToastContainer({ toasts, onRemove }: { toasts: Toast[]; onRemove: (id: number) => void }) {
  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-20 left-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onRemove={onRemove} />
      ))}
    </div>
  )
}

function ToastItem({ toast, onRemove }: { toast: Toast; onRemove: (id: number) => void }) {
  const [isExiting, setIsExiting] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsExiting(true)
    }, 3000)

    return () => clearTimeout(timer)
  }, [])

  useEffect(() => {
    if (isExiting) {
      const timer = setTimeout(() => {
        onRemove(toast.id)
      }, 200)
      return () => clearTimeout(timer)
    }
  }, [isExiting, onRemove, toast.id])

  const handleClose = () => {
    setIsExiting(true)
  }

  return (
    <div
      className={`
        pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg
        ${toast.type === 'error' ? 'bg-red-500 text-white' : 'bg-green-500 text-white'}
        ${isExiting ? 'toast-exit' : 'toast-enter'}
      `}
      style={{
        animation: isExiting ? 'toastExit 200ms ease-out forwards' : 'toastEnter 200ms ease-out',
      }}
    >
      <span className="flex-1 text-sm font-medium">{toast.message}</span>
      <button
        onClick={handleClose}
        className="p-1 rounded-full hover:bg-white/20 transition-colors"
      >
        <X size={16} />
      </button>
    </div>
  )
}
