/**
 * pages/BillingSuccess.jsx
 * ────────────────────────
 * Where Stripe sends people after paying. IMPORTANT: landing here proves nothing
 * by itself — the plan only changes once the backend has confirmed it with Stripe.
 * So we (1) ask the server to pull the subscription straight from Stripe, then
 * (2) poll briefly in case that races the webhook, and only then celebrate.
 */
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, Loader2, AlertTriangle } from 'lucide-react'
import { syncBilling, getBillingStatus } from '../services/billingApi'
import { useAuth } from '../context/AuthContext'

const MAX_ATTEMPTS = 8
const DELAY_MS = 2000

export default function BillingSuccess() {
  const { refreshUser } = useAuth()
  const [state, setState] = useState('checking')     // checking | done | delayed | error
  const [plan, setPlan] = useState('')
  const [error, setError] = useState('')
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return undefined           // React 18 StrictMode runs effects twice in dev
    started.current = true
    let cancelled = false

    const finish = async (s) => {
      await refreshUser().catch(() => {})
      if (!cancelled) { setPlan(s.plan_name); setState('done') }
    }

    ;(async () => {
      try {
        let s = await syncBilling()
        if (s.plan !== 'free') return finish(s)
        for (let i = 0; i < MAX_ATTEMPTS && !cancelled; i += 1) {
          await new Promise((r) => setTimeout(r, DELAY_MS))
          s = await getBillingStatus()
          if (s.plan !== 'free') return finish(s)
        }
        if (!cancelled) setState('delayed')
      } catch (e) {
        if (!cancelled) { setError(e.message); setState('error') }
      }
      return undefined
    })()

    return () => { cancelled = true }
  }, [refreshUser])

  const box = 'flex flex-col items-center text-center gap-4 max-w-md mx-auto'
  return (
    <div className="flex-1 flex items-center justify-center p-8 page-enter">
      {state === 'checking' && (
        <div className={box}>
          <Loader2 size={36} className="animate-spin" style={{ color: 'var(--accent)' }} />
          <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Confirming your payment…</h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>This usually takes a few seconds. Please don&apos;t close this page.</p>
        </div>
      )}
      {state === 'done' && (
        <div className={box}>
          <CheckCircle2 size={44} style={{ color: '#22c55e' }} />
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>You&apos;re on {plan}!</h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Payment confirmed. Your new limits are active right now.</p>
          <div className="flex gap-2 mt-2">
            <Link to="/upload" className="btn-primary">Upload data</Link>
            <Link to="/billing" className="btn-ghost">View billing</Link>
          </div>
        </div>
      )}
      {state === 'delayed' && (
        <div className={box}>
          <AlertTriangle size={40} style={{ color: '#f59e0b' }} />
          <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Still confirming</h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Stripe hasn&apos;t confirmed the payment yet. If you were charged, your plan will update automatically within a minute or two.
          </p>
          <Link to="/billing" className="btn-primary mt-2">Check billing</Link>
        </div>
      )}
      {state === 'error' && (
        <div className={box}>
          <AlertTriangle size={40} style={{ color: '#ef4444' }} />
          <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Couldn&apos;t confirm your plan</h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{error}</p>
          <Link to="/billing" className="btn-primary mt-2">Go to billing</Link>
        </div>
      )}
    </div>
  )
}
