/**
 * ConfirmDialog.jsx — small modal used before billing actions that cost money
 * or reduce access (plan change, cancel). Closes on Escape or backdrop click.
 */
import { useEffect } from 'react'
import { Loader2 } from 'lucide-react'

export default function ConfirmDialog({
  open, title, message, confirmLabel = 'Confirm', danger = false, busy = false, onConfirm, onCancel,
}) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onCancel() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, busy, onCancel])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: 'rgba(0,0,0,0.65)' }} onClick={() => !busy && onCancel()}>
      <div className="card p-6 w-full max-w-md page-enter" role="dialog" aria-modal="true"
        onClick={(e) => e.stopPropagation()}>
        <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>{title}</h3>
        <p className="text-sm mb-5" style={{ color: 'var(--text-secondary)' }}>{message}</p>
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onCancel} disabled={busy}>Keep things as they are</button>
          <button className="btn-primary" onClick={onConfirm} disabled={busy}
            style={danger ? { background: '#dc2626' } : undefined}>
            {busy && <Loader2 size={14} className="animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
