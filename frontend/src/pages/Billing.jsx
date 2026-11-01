/**
 * pages/Billing.jsx
 * ─────────────────
 * Account billing hub: current plan + renewal, dataset usage, payment-method /
 * invoice management (Stripe portal), cancel / resume, and invoice history.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CreditCard, ExternalLink, Loader2, Receipt } from 'lucide-react'
import {
  getBillingStatus, getBillingHistory, openBillingPortal, cancelSubscription, resumeSubscription,
} from '../services/billingApi'
import { useAuth } from '../context/AuthContext'
import ConfirmDialog from '../components/ConfirmDialog'
import Banner from '../components/Banner'
import { formatDate, formatMoney } from '../utils/format'

const STATUS_STYLE = {
  active:   ['Active', 'rgba(34,197,94,0.12)', '#4ade80'],
  trialing: ['Trial', 'rgba(14,165,233,0.12)', '#38bdf8'],
  past_due: ['Payment failed', 'rgba(239,68,68,0.12)', '#f87171'],
  none:     ['Free', 'rgba(255,255,255,0.06)', '#8892a4'],
  canceled: ['Canceled', 'rgba(255,255,255,0.06)', '#8892a4'],
}

function Pill({ children, bg, color }) {
  return <span className="text-xs font-semibold px-2 py-0.5 rounded-md" style={{ background: bg, color }}>{children}</span>
}

export default function Billing() {
  const { refreshUser } = useAuth()
  const [status, setStatus] = useState(null)
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [confirmCancel, setConfirmCancel] = useState(false)

  const load = useCallback(async () => {
    try {
      const [s, h] = await Promise.all([getBillingStatus(), getBillingHistory()])
      setStatus(s); setInvoices(h.invoices)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load])

  const act = async (fn, msg) => {
    setBusy(true); setError(''); setNotice('')
    try { await fn(); if (msg) setNotice(msg); await Promise.all([load(), refreshUser()]) }
    catch (e) { setError(e.message) }
    finally { setBusy(false); setConfirmCancel(false) }
  }

  const portal = async () => {
    setBusy(true); setError('')
    try { const { url } = await openBillingPortal(); window.location.href = url }
    catch (e) { setError(e.message); setBusy(false) }
  }

  if (loading) return <div className="p-8"><div className="skeleton h-72 w-full max-w-3xl mx-auto rounded-2xl" /></div>
  if (!status) return <div className="p-8 max-w-3xl mx-auto"><Banner tone="error">{error || 'Could not load billing.'}</Banner></div>

  const paid = status.plan !== 'free'
  const [statusLabel, statusBg, statusColor] = STATUS_STYLE[status.subscription_status] || STATUS_STYLE.none
  const limit = status.upload_limit
  const pct = limit ? Math.min(100, Math.round((status.uploads_used / limit) * 100)) : 0
  const barColor = pct >= 100 ? '#ef4444' : pct >= 70 ? '#f59e0b' : 'var(--accent)'

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8 page-enter">
      <div className="max-w-3xl mx-auto space-y-5">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Billing</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>Manage your plan, payment method and invoices.</p>
        </div>

        {error && <Banner tone="error">{error}</Banner>}
        {notice && <Banner tone="ok">{notice}</Banner>}
        {status.subscription_status === 'past_due' && (
          <Banner tone="error">
            Your last payment didn&apos;t go through. Update your card to keep your {status.plan_name} plan.{' '}
            <button className="underline font-medium" onClick={portal}>Update payment method</button>
          </Banner>
        )}
        {status.over_limit && (
          <Banner tone="warn">
            You have {status.uploads_used} datasets but the {status.plan_name} plan allows {limit}. Nothing was deleted —
            you just can&apos;t add more until you upgrade or remove some.
          </Banner>
        )}

        {/* Current plan */}
        <div className="card p-6">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="section-label mb-1">Current plan</p>
              <div className="flex items-center gap-2.5">
                <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>{status.plan_name}</h2>
                <Pill bg={statusBg} color={statusColor}>{statusLabel}</Pill>
                {status.cancel_at_period_end && <Pill bg="rgba(245,158,11,0.12)" color="#fbbf24">Cancels {formatDate(status.current_period_end)}</Pill>}
              </div>
              <p className="text-sm mt-1.5" style={{ color: 'var(--text-secondary)' }}>
                {paid
                  ? `${formatMoney(status.price_cents)} / month · ${status.cancel_at_period_end ? 'access until' : 'renews'} ${formatDate(status.current_period_end)}`
                  : 'Free forever — upgrade any time.'}
              </p>
            </div>
            <Link to="/pricing" className="btn-primary">{paid ? 'Change plan' : 'Upgrade'}</Link>
          </div>

          <div className="mt-6">
            <div className="flex justify-between text-xs mb-1.5" style={{ color: 'var(--text-muted)' }}>
              <span>Datasets used</span>
              <span className="stat-number">{status.uploads_used} / {limit === null ? 'Unlimited' : limit}</span>
            </div>
            <div className="h-2 rounded-full" style={{ background: 'var(--bg-elevated)' }}>
              <div className="h-2 rounded-full transition-all" style={{ width: limit === null ? '8%' : `${pct}%`, background: barColor }} />
            </div>
          </div>

          {(status.has_billing_account || paid) && (
            <div className="flex flex-wrap gap-2 mt-6 pt-5 border-t" style={{ borderColor: 'var(--border)' }}>
              {status.has_billing_account && (
                <button className="btn-ghost" onClick={portal} disabled={busy}>
                  <CreditCard size={15} /> Payment method &amp; invoices <ExternalLink size={12} />
                </button>
              )}
              {paid && !status.cancel_at_period_end && (
                <button className="btn-ghost" onClick={() => setConfirmCancel(true)} disabled={busy}>Cancel subscription</button>
              )}
              {paid && status.cancel_at_period_end && (
                <button className="btn-primary" disabled={busy}
                  onClick={() => act(resumeSubscription, 'Welcome back — your subscription will continue.')}>
                  {busy && <Loader2 size={14} className="animate-spin" />} Resume subscription
                </button>
              )}
            </div>
          )}
        </div>

        {/* History */}
        <div className="card p-6">
          <div className="flex items-center gap-2 mb-4">
            <Receipt size={16} style={{ color: 'var(--text-muted)' }} />
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Billing history</h3>
          </div>
          {invoices.length === 0 ? (
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No invoices yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs" style={{ color: 'var(--text-muted)' }}>
                    <th className="pb-2 font-medium">Date</th><th className="pb-2 font-medium">Plan</th>
                    <th className="pb-2 font-medium">Amount</th><th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium text-right">Invoice</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
                    <tr key={inv.id} className="border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
                      <td className="py-2.5">{formatDate(inv.date)}</td>
                      <td className="py-2.5 capitalize">{inv.plan || '—'}</td>
                      <td className="py-2.5 stat-number">{formatMoney(inv.amount_cents, inv.currency)}</td>
                      <td className="py-2.5">
                        <Pill bg={inv.status === 'paid' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)'}
                          color={inv.status === 'paid' ? '#4ade80' : '#f87171'}>{inv.status === 'paid' ? 'Paid' : 'Failed'}</Pill>
                      </td>
                      <td className="py-2.5 text-right">
                        {inv.invoice_url
                          ? <a href={inv.invoice_url} target="_blank" rel="noopener noreferrer" className="hover:underline" style={{ color: 'var(--accent)' }}>View</a>
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmCancel} busy={busy} danger
        title="Cancel your subscription?"
        message={`You'll keep ${status.plan_name} until ${formatDate(status.current_period_end)}, then move to the Free plan. Your data is never deleted, and you can resume any time before then.`}
        confirmLabel="Cancel subscription"
        onConfirm={() => act(cancelSubscription, 'Cancellation scheduled — you keep access until the period ends.')}
        onCancel={() => setConfirmCancel(false)}
      />
    </div>
  )
}
