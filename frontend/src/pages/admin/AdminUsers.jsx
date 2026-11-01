/**
 * pages/admin/AdminUsers.jsx — every customer: search, filter, paginate. Click a row for details.
 */
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, ChevronLeft, ChevronRight } from 'lucide-react'
import { listAdminUsers } from '../../services/adminApi'
import Banner from '../../components/Banner'
import { formatDate } from '../../utils/format'

const PLAN_STYLE = {
  free: ['rgba(255,255,255,0.06)', '#8892a4'],
  starter: ['rgba(14,165,233,0.14)', '#38bdf8'],
  pro: ['rgba(245,158,11,0.14)', '#fbbf24'],
}

export function Pill({ children, bg, color }) {
  return <span className="text-xs font-semibold px-2 py-0.5 rounded-md whitespace-nowrap" style={{ background: bg, color }}>{children}</span>
}

export function PlanPill({ plan }) {
  const [bg, color] = PLAN_STYLE[plan] || PLAN_STYLE.free
  return <Pill bg={bg} color={color}>{plan.toUpperCase()}</Pill>
}

export function StatusPill({ user }) {
  if (!user.is_active) return <Pill bg="rgba(239,68,68,0.14)" color="#f87171">Suspended</Pill>
  if (user.subscription_status === 'past_due') return <Pill bg="rgba(239,68,68,0.14)" color="#f87171">Payment failed</Pill>
  if (user.cancel_at_period_end) return <Pill bg="rgba(245,158,11,0.14)" color="#fbbf24">Cancelling</Pill>
  return <Pill bg="rgba(34,197,94,0.12)" color="#4ade80">Active</Pill>
}

export default function AdminUsers() {
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')            // debounced copy of `search`
  const [plan, setPlan] = useState('all')
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const reqId = useRef(0)

  // wait for the person to stop typing before hitting the API
  useEffect(() => {
    const t = setTimeout(() => { setQuery(search.trim()); setPage(1) }, 300)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    const id = ++reqId.current
    setLoading(true)
    listAdminUsers({ page, limit: 20, search: query, plan, status })
      .then((d) => { if (id === reqId.current) { setData(d); setError('') } })        // ignore out-of-date responses
      .catch((e) => { if (id === reqId.current) setError(e.message) })
      .finally(() => { if (id === reqId.current) setLoading(false) })
  }, [page, query, plan, status])

  const select = 'input !w-auto text-sm'
  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8 page-enter">
      <div className="max-w-6xl mx-auto space-y-5">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Customers</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>{data ? `${data.total} account${data.total === 1 ? '' : 's'}` : ' '}</p>
        </div>

        <div className="flex flex-wrap gap-3">
          <div className="relative flex-1 min-w-[220px]">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
            <input className="input pl-9" placeholder="Search name, email or organisation…" aria-label="Search customers"
              value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <select className={select} aria-label="Filter by plan" value={plan} onChange={(e) => { setPlan(e.target.value); setPage(1) }}>
            <option value="all">All plans</option><option value="free">Free</option><option value="starter">Starter</option><option value="pro">Pro</option>
          </select>
          <select className={select} aria-label="Filter by status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}>
            <option value="all">Any status</option><option value="active">Active</option><option value="past_due">Payment failed</option><option value="suspended">Suspended</option>
          </select>
        </div>

        {error && <Banner tone="error">{error}</Banner>}

        <div className="card overflow-x-auto" style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .15s' }}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs" style={{ color: 'var(--text-muted)' }}>
                {['Customer', 'Organisation', 'Plan', 'Status', 'Datasets', 'Joined', 'Last login'].map((h) => (
                  <th key={h} className="px-4 py-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data?.users.map((u) => (
                <tr key={u.id} className="border-t hover:bg-white/[0.03]" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
                  <td className="px-4 py-3">
                    <Link to={`/admin/users/${u.id}`} className="font-medium hover:underline" style={{ color: 'var(--text-primary)' }}>{u.name}</Link>
                    {u.role === 'admin' && <span className="ml-2 text-[10px] font-bold px-1.5 py-0.5 rounded" style={{ background: 'rgba(245,158,11,0.15)', color: '#fbbf24' }}>ADMIN</span>}
                    <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{u.email}</div>
                  </td>
                  <td className="px-4 py-3">{u.organization || '—'}</td>
                  <td className="px-4 py-3"><PlanPill plan={u.plan} /></td>
                  <td className="px-4 py-3"><StatusPill user={u} /></td>
                  <td className="px-4 py-3 stat-number">{u.datasets}</td>
                  <td className="px-4 py-3">{formatDate(u.created_at)}</td>
                  <td className="px-4 py-3">{formatDate(u.last_login_at)}</td>
                </tr>
              ))}
              {data && data.users.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-10 text-center" style={{ color: 'var(--text-muted)' }}>No customers match.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {data && data.pages > 1 && (
          <div className="flex items-center justify-between text-sm" style={{ color: 'var(--text-muted)' }}>
            <span>Page {data.page} of {data.pages}</span>
            <div className="flex gap-2">
              <button className="btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page"><ChevronLeft size={15} /> Prev</button>
              <button className="btn-ghost" disabled={page >= data.pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page">Next <ChevronRight size={15} /></button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
