/**
 * pages/admin/AdminOverview.jsx — the founder's at-a-glance dashboard.
 * Every number comes from /api/admin/stats (real data — nothing hard-coded).
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar } from 'react-chartjs-2'
import 'chart.js/auto'
import { Users, DollarSign, TrendingDown, Database, UserPlus, Activity, CreditCard } from 'lucide-react'
import { getAdminStats } from '../../services/adminApi'
import Banner from '../../components/Banner'
import { formatMoney, monthLabel } from '../../utils/format'

const GRID = 'rgba(255,255,255,0.05)'
const TICK = '#6b7280'

function Stat({ icon: Icon, label, value, sub, tone = 'var(--accent)' }) {
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg" style={{ background: 'var(--bg-elevated)' }}>
          <Icon size={15} style={{ color: tone }} />
        </div>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
      </div>
      <div className="text-2xl font-bold stat-number" style={{ color: 'var(--text-primary)' }}>{value}</div>
      {sub && <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{sub}</div>}
    </div>
  )
}

function MonthlyBars({ title, rows, valueKey, color, format }) {
  const data = {
    labels: rows.map((r) => monthLabel(r.month)),
    datasets: [{ data: rows.map((r) => r[valueKey]), backgroundColor: color, borderRadius: 6, maxBarThickness: 36 }],
  }
  const options = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => format(c.raw) } } },
    scales: {
      x: { grid: { display: false }, ticks: { color: TICK } },
      y: { beginAtZero: true, grid: { color: GRID }, border: { display: false }, ticks: { color: TICK, callback: (v) => format(v) } },
    },
  }
  return (
    <div className="card p-5">
      <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>{title}</h3>
      <div style={{ height: 220 }}><Bar data={data} options={options} /></div>
    </div>
  )
}

export default function AdminOverview() {
  const [s, setS] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { getAdminStats().then(setS).catch((e) => setError(e.message)) }, [])

  if (error) return <div className="p-8"><Banner tone="error">{error}</Banner></div>
  if (!s) return <div className="p-8"><div className="skeleton h-96 rounded-2xl" /></div>

  const money = (c) => formatMoney(c)
  const attention = s.past_due + s.pending_cancellations + s.suspended_users

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8 page-enter">
      <div className="max-w-6xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Business overview</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>Live numbers for the whole platform.</p>
        </div>

        {attention > 0 && (
          <Banner tone="warn">
            Needs attention:{' '}
            {s.past_due > 0 && <>{s.past_due} payment{s.past_due > 1 ? 's' : ''} failing · </>}
            {s.pending_cancellations > 0 && <>{s.pending_cancellations} cancelling at period end · </>}
            {s.suspended_users > 0 && <>{s.suspended_users} suspended · </>}
            <Link to="/admin/users" className="underline font-medium">view customers</Link>
          </Banner>
        )}

        <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
          <Stat icon={DollarSign} label="Monthly recurring revenue" value={money(s.mrr_cents)}
            sub={`${s.paying_by_plan.starter} Starter · ${s.paying_by_plan.pro} Pro`} tone="#22c55e" />
          <Stat icon={CreditCard} label="Paying customers" value={s.paying_customers} sub={`${s.total_users} total accounts`} />
          <Stat icon={DollarSign} label="Revenue (30 days)" value={money(s.revenue_30d_cents)} sub={`${money(s.revenue_total_cents)} all time`} tone="#22c55e" />
          <Stat icon={TrendingDown} label="Churn (30 days)"
            value={s.churn_rate_30d === null ? '—' : `${s.churn_rate_30d}%`}
            sub={`${s.canceled_30d} cancellation${s.canceled_30d === 1 ? '' : 's'}`} tone="#f59e0b" />
        </div>
        <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
          <Stat icon={UserPlus} label="New sign-ups (7 days)" value={s.new_users_7d} sub={`${s.new_users_30d} in 30 days`} />
          <Stat icon={Activity} label="Active users (30 days)" value={s.active_users_30d} sub="logged in" />
          <Stat icon={Database} label="Datasets uploaded" value={s.total_datasets} sub={`${s.datasets_30d} in 30 days`} />
          <Stat icon={Users} label="Plan mix" value={`${s.plan_counts.free} / ${s.plan_counts.starter} / ${s.plan_counts.pro}`} sub="Free / Starter / Pro" />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <MonthlyBars title="New sign-ups per month" rows={s.signups_by_month} valueKey="count" color="#0ea5e9" format={(v) => String(v)} />
          <MonthlyBars title="Revenue collected per month" rows={s.revenue_by_month} valueKey="cents" color="#22c55e" format={money} />
        </div>

        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          MRR counts customers with a live Stripe subscription (manually granted plans are excluded). Stripe stays the source of truth.
        </p>
      </div>
    </div>
  )
}
