/**
 * pages/Pricing.jsx
 * ─────────────────
 * Plan picker. The button on each card depends on where the user is now:
 *   Free  → Starter/Pro : "Upgrade"  → Stripe Checkout
 *   Paid  → other paid  : "Switch"   → prorated plan change (confirm first)
 *   Paid  → Free        : "Downgrade"→ cancel at period end (confirm first)
 * Prices, limits and features come from the API, so there is one source of truth.
 */
import { useCallback, useEffect, useState } from 'react'
import { Check, Loader2, Sparkles } from 'lucide-react'
import { getPlans, getBillingStatus, startCheckout, changePlan, cancelSubscription } from '../services/billingApi'
import { useAuth } from '../context/AuthContext'
import ConfirmDialog from '../components/ConfirmDialog'
import Banner from '../components/Banner'
import { formatDate, formatMoney } from '../utils/format'

const ORDER = ['free', 'starter', 'pro']

export default function Pricing() {
  const { refreshUser } = useAuth()
  const [plans, setPlans] = useState([])
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [confirm, setConfirm] = useState(null)   // { title, message, confirmLabel, danger, run }

  const load = useCallback(async () => {
    try {
      const [p, s] = await Promise.all([getPlans(), getBillingStatus()])
      setPlans(p.plans)
      setStatus(s)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const run = async (fn, successMsg) => {
    setBusy(true); setError(''); setNotice('')
    try {
      await fn()
      if (successMsg) setNotice(successMsg)
      await Promise.all([load(), refreshUser()])
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false); setConfirm(null)
    }
  }

  const goCheckout = async (plan) => {
    setBusy(true); setError('')
    try {
      const { url } = await startCheckout(plan)
      window.location.href = url          // off to Stripe's hosted checkout page
    } catch (e) {
      setError(e.message); setBusy(false)
    }
  }

  const onSelect = (plan) => {
    const current = status.plan
    if (plan.id === current) return
    const name = plan.name

    if (plan.id === 'free') {
      setConfirm({
        title: 'Downgrade to Free?',
        message: `You keep your ${status.plan_name} features until ${formatDate(status.current_period_end)}, ` +
                 `then move to Free (1 dataset). Your existing data is never deleted.`,
        confirmLabel: 'Schedule downgrade', danger: true,
        run: () => run(cancelSubscription, 'Done — your plan will switch to Free when the current period ends.'),
      })
    } else if (current === 'free') {
      goCheckout(plan.id)
    } else {
      const up = ORDER.indexOf(plan.id) > ORDER.indexOf(current)
      setConfirm({
        title: `Switch to ${name}?`,
        message: up
          ? `You'll be charged the prorated difference now and get ${name} features immediately.`
          : `You'll move to ${name} right away and receive a prorated credit on your next invoice.`,
        confirmLabel: `Switch to ${name}`,
        run: () => run(() => changePlan(plan.id), `You're now on ${name}.`),
      })
    }
  }

  if (loading) {
    return <div className="p-8"><div className="skeleton h-64 w-full max-w-4xl mx-auto rounded-2xl" /></div>
  }

  const configured = status?.billing_configured
  const current = status?.plan

  const buttonFor = (plan) => {
    if (plan.id === current) {
      const pending = status.cancel_at_period_end && current !== 'free'
      return { label: pending ? `Ends ${formatDate(status.current_period_end)}` : 'Current plan', disabled: true }
    }
    if (plan.id === 'free') return { label: 'Downgrade to Free', disabled: !configured || current === 'free' }
    if (current === 'free') return { label: `Upgrade to ${plan.name}`, disabled: !configured, primary: true }
    const up = ORDER.indexOf(plan.id) > ORDER.indexOf(current)
    return { label: `${up ? 'Upgrade' : 'Switch'} to ${plan.name}`, disabled: !configured, primary: up }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8 page-enter">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Choose your plan</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
            Upgrade, downgrade or cancel any time. Prices in USD, billed monthly.
          </p>
        </div>

        {!configured && (
          <Banner tone="warn">
            Billing isn&apos;t set up on this server yet, so paid plans can&apos;t be purchased. See STRIPE_SETUP.md.
          </Banner>
        )}
        {error && <Banner tone="error">{error}</Banner>}
        {notice && <Banner tone="ok">{notice}</Banner>}
        {status?.over_limit && (
          <Banner tone="warn">
            You have {status.uploads_used} datasets but your plan allows {status.upload_limit}. Your data is safe —
            you just can&apos;t upload more until you upgrade or delete some.
          </Banner>
        )}

        <div className="grid gap-5 md:grid-cols-3">
          {plans.map((plan) => {
            const btn = buttonFor(plan)
            const isCurrent = plan.id === current
            return (
              <div key={plan.id} className="card p-6 flex flex-col relative"
                style={{
                  borderColor: plan.popular ? 'var(--accent)' : isCurrent ? 'rgba(255,255,255,0.18)' : undefined,
                  boxShadow: plan.popular ? '0 0 0 1px var(--accent)' : undefined,
                }}>
                {plan.popular && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 flex items-center gap-1 text-xs font-semibold px-3 py-1 rounded-full"
                    style={{ background: 'var(--accent)', color: '#fff' }}>
                    <Sparkles size={11} /> Most popular
                  </span>
                )}
                <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>{plan.name}</h2>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{plan.tagline}</p>

                <div className="mt-4 mb-5 flex items-baseline gap-1">
                  <span className="text-4xl font-bold stat-number" style={{ color: 'var(--text-primary)' }}>
                    {formatMoney(plan.price_cents)}
                  </span>
                  <span className="text-sm" style={{ color: 'var(--text-muted)' }}>{plan.price_cents ? '/ month' : 'forever'}</span>
                </div>

                <ul className="space-y-2.5 mb-6 flex-1">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <Check size={15} className="mt-0.5 shrink-0" style={{ color: 'var(--accent)' }} />
                      {f}
                    </li>
                  ))}
                </ul>

                <button
                  className={btn.primary ? 'btn-primary justify-center' : 'btn-ghost justify-center'}
                  disabled={btn.disabled || busy}
                  onClick={() => onSelect(plan)}
                  style={btn.disabled ? { opacity: isCurrent ? 1 : 0.5, cursor: 'default' } : undefined}>
                  {busy && !btn.disabled && <Loader2 size={14} className="animate-spin" />}
                  {btn.label}
                </button>
              </div>
            )
          })}
        </div>

        <p className="text-center text-xs mt-6" style={{ color: 'var(--text-muted)' }}>
          Payments are processed securely by Stripe. We never see or store your card details.
        </p>
      </div>

      <ConfirmDialog
        open={!!confirm} busy={busy}
        title={confirm?.title} message={confirm?.message}
        confirmLabel={confirm?.confirmLabel} danger={confirm?.danger}
        onConfirm={() => confirm?.run()} onCancel={() => setConfirm(null)}
      />
    </div>
  )
}
