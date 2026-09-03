import { useEffect } from 'react'
import { CheckCircle2, CircleAlert, X } from 'lucide-react'

function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return undefined
    const timer = window.setTimeout(onClose, 5000)
    return () => window.clearTimeout(timer)
  }, [toast, onClose])

  if (!toast) return null
  const success = toast.type === 'success'
  const Icon = success ? CheckCircle2 : CircleAlert

  return (
    <div className="fixed bottom-5 left-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 animate-[toast-in_250ms_ease-out] sm:left-auto sm:right-5 sm:translate-x-0">
      <div className={`flex items-start gap-3 rounded-2xl border bg-white p-4 shadow-xl shadow-slate-900/10 ${success ? 'border-emerald-200' : 'border-rose-200'}`}>
        <Icon className={success ? 'text-emerald-600' : 'text-rose-600'} size={20} />
        <p className="min-w-0 flex-1 text-sm font-medium leading-5 text-slate-700">{toast.message}</p>
        <button type="button" aria-label="Dismiss message" className="text-slate-400 hover:text-slate-700" onClick={onClose}>
          <X size={17} />
        </button>
      </div>
    </div>
  )
}

export default Toast
