/**
 * pages/admin/AdminUserDetail.jsx — one customer: profile, billing, datasets, invoices, and the
 * (guarded) actions: suspend / restore, grant a plan, delete.
 *
 * The server enforces every rule shown here (can't touch admins or yourself, can't delete or
 * re-plan someone Stripe is billing). The disabled buttons just explain *why* up front.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2, Trash2 } from 'lucide-react'
import { getAdminUser, suspendUser, restoreUser, setUserPlan, deleteUser } from '../../services/adminApi'
import { useAuth } from '../../context/AuthContext'
import ConfirmDialog from '../../components/ConfirmDialog'
import Banner from '../../components/Banner'
import { formatDate, formatMoney } from '../../utils/format'
import { PlanPill, StatusPill, Pill } from './AdminUsers'

function DeleteDialog({ email, busy, onConfirm, onCancel }) {
  const [typed, setTyped] = useState('')
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4" style={{ background: 'rgba(0,0,0,0.65)' }}
      onClick={() => !busy && onCancel()}>
      <div className="card p-6 w-full max-w-md" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-base font-semibold mb-2" style={{ color: '#f87171' }}>Delete this customer permanently?</h3>
        <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
          This removes the account, all their datasets (including the files) and billing history. It cannot be undone.
          Type <strong style={{ color: 'var(--text-primary)' }}>{email}</strong> to confirm.
        </p>
        <input className="input mb-5" value={typed} onChange={(e) => setTyped(e.target.value)} aria-label="Type the email to confirm" autoFocus />
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className="btn-primary" style={{ background: '#dc2626' }} disabled={busy || typed.trim().toLowerCase() !== email.toLowerCase()} onClick={onConfirm}>
            {busy && <Loader2 size={14} className="animate-spin" />} Delete forever
          </button>
        </div>
      </div>
    </div>
  )
}

export default function AdminUserDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user: me } = useAuth()
  const [d, setD] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [plan, setPlan] = useState('free')
  const [dialog, setDialog] = useState(null)         // 'suspend' | 'plan' | 'delete'

  const load = useCallback(async () => {
    try { const data = await getAdminUser(id); setD(data); setPlan(data.user.plan) }
    catch (e) { setError(e.message) }
  }, [id])
  useEffect(() => { load() }, [load])

  const run = async (fn, msg, after) => {
    setBusy(true); setError(''); setNotice('')
    try { await fn(); if (msg) setNotice(msg); await load(); if (after) after() }
    catch (e) { setError(e.message) }
    finally { setBusy(false); setDialog(null) }
  }

  if (!d) {
    return <div className="p-8 max-w-4xl mx-auto">{error ? <Banner tone="error">{error}</Banner> : <div className="skeleton h-96 rounded-2xl" />}</div>
  }

  const u = d.user
  const isSelf = me?.id === u.id
  const isAdminAccount = u.role === 'admin'
  const locked = isSelf || isAdminAccount
  const lockReason = isSelf ? 'This is your own account.' : 'Admin accounts are managed from the server (scripts/manage_users.py).'

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8 page-enter">
      <div className="max-w-4xl mx-auto space-y-5">
        <Link to="/admin/users" className="inline-flex items-center gap-1 text-sm hover:underline" style={{ color: 'var(--text-muted)' }}>
          <ArrowLeft size={14} /> All customers
        </Link>

        {error && <Banner tone="error">{error}</Banner>}
        {notice && <Banner tone="ok">{notice}</Banner>}

        <div className="card p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2.5 flex-wrap">
                <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{u.name}</h1>
                {isAdminAccount && <Pill bg="rgba(245,158,11,0.15)" color="#fbbf24">ADMIN</Pill>}
                <PlanPill plan={u.plan} /> <StatusPill user={u} />
              </div>
              <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>{u.email}</p>
              {u.organization && <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{u.organization}</p>}
            </div>
            <dl className="text-xs grid grid-cols-2 gap-x-6 gap-y-1" style={{ color: 'var(--text-muted)' }}>
              <dt>Joined</dt><dd style={{ color: 'var(--text-secondary)' }}>{formatDate(u.created_at)}</dd>
              <dt>Last login</dt><dd style={{ color: 'var(--text-secondary)' }}>{formatDate(u.last_login_at)}</dd>
              <dt>Datasets</dt><dd style={{ color: 'var(--text-secondary)' }}>{u.datasets}</dd>
              <dt>Billing</dt>
              <dd style={{ color: 'var(--text-secondary)' }}>
                {d.has_stripe_subscription ? `Stripe · renews ${formatDate(d.billing.current_period_end)}` : 'No Stripe subscription'}
              </dd>
            </dl>
          </div>
        </div>

        <div className="card p-6">
          <h2 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Actions</h2>
          {locked && <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>{lockReason}</p>}

          <div className="flex flex-wrap items-center gap-3 mt-3">
            {u.is_active
              ? <button className="btn-ghost" disabled={locked || busy} onClick={() => setDialog('suspend')}>Suspend account</button>
              : <button className="btn-primary" disabled={locked || busy} onClick={() => run(() => restoreUser(u.id), 'Account restored.')}>Restore account</button>}

            <div className="flex items-center gap-2">
              <select className="input !w-auto text-sm" aria-label="Plan" value={plan} onChange={(e) => setPlan(e.target.value)}
                disabled={locked || busy || d.has_stripe_subscription}>
                <option value="free">Free</option><option value="starter">Starter</option><option value="pro">Pro</option>
              </select>
              <button className="btn-ghost" disabled={locked || busy || d.has_stripe_subscription || plan === u.plan} onClick={() => setDialog('plan')}>
                Set plan
              </button>
            </div>

            <button className="btn-ghost ml-auto" style={{ color: '#f87171' }} disabled={locked || busy || d.has_stripe_subscription} onClick={() => setDialog('delete')}>
              <Trash2 size={14} /> Delete…
            </button>
          </div>
          {d.has_stripe_subscription && !locked && (
            <p className="text-xs mt-3" style={{ color: 'var(--text-muted)' }}>
              This customer is paying through Stripe. Change or cancel their subscription in Stripe first — then plan changes and deletion unlock here.
            </p>
          )}
          {!d.has_stripe_subscription && !locked && (
            <p className="text-xs mt-3" style={{ color: 'var(--text-muted)' }}>
              &ldquo;Set plan&rdquo; grants a plan without payment (e.g. a trial or partner account).
            </p>
          )}
        </div>

        <div className="card p-6">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Datasets</h2>
          {d.datasets.length === 0 ? <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No uploads yet.</p> : (
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs" style={{ color: 'var(--text-muted)' }}><th className="pb-2 font-medium">File</th><th className="pb-2 font-medium">Rows</th><th className="pb-2 font-medium">Uploaded</th></tr></thead>
              <tbody>
                {d.datasets.map((f) => (
                  <tr key={f.id} className="border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
                    <td className="py-2">{f.name}</td><td className="py-2 stat-number">{f.rows?.toLocaleString() ?? '—'}</td><td className="py-2">{formatDate(f.uploaded_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card p-6">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Invoices</h2>
          {d.invoices.length === 0 ? <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No invoices.</p> : (
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs" style={{ color: 'var(--text-muted)' }}><th className="pb-2 font-medium">Date</th><th className="pb-2 font-medium">Plan</th><th className="pb-2 font-medium">Amount</th><th className="pb-2 font-medium">Status</th></tr></thead>
              <tbody>
                {d.invoices.map((i) => (
                  <tr key={i.id} className="border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
                    <td className="py-2">{formatDate(i.date)}</td><td className="py-2 capitalize">{i.plan || '—'}</td>
                    <td className="py-2 stat-number">{formatMoney(i.amount_cents, i.currency)}</td>
                    <td className="py-2">{i.status === 'paid' ? 'Paid' : 'Failed'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <ConfirmDialog open={dialog === 'suspend'} busy={busy} danger title={`Suspend ${u.name}?`}
        message="They are signed out immediately and can't log in until you restore the account. Their data is kept."
        confirmLabel="Suspend" onCancel={() => setDialog(null)}
        onConfirm={() => run(() => suspendUser(u.id), 'Account suspended.')} />
      <ConfirmDialog open={dialog === 'plan'} busy={busy} title={`Set plan to ${plan}?`}
        message={`${u.name} will get the ${plan} plan limits right away, without being charged.`}
        confirmLabel="Set plan" onCancel={() => setDialog(null)}
        onConfirm={() => run(() => setUserPlan(u.id, plan), `Plan set to ${plan}.`)} />
      {dialog === 'delete' && (
        <DeleteDialog email={u.email} busy={busy} onCancel={() => setDialog(null)}
          onConfirm={() => run(() => deleteUser(u.id), null, () => navigate('/admin/users', { replace: true }))} />
      )}
    </div>
  )
}
