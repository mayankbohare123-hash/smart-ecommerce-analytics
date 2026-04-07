/**
 * KPICards.jsx
 * ────────────
 * Six KPI cards shown at the top of the dashboard.
 * Each card animates in with a staggered delay.
 */
import { DollarSign, ShoppingCart, Users, TrendingUp, Package, MapPin } from 'lucide-react'

const fmt = {
  currency: (v) => `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`,
  number:   (v) => Number(v).toLocaleString('en-US'),
  percent:  (v) => v != null ? `${v > 0 ? '+' : ''}${v.toFixed(1)}%` : '—',
}

const CARDS = [
  {
    key: 'total_revenue',
    label: 'Total Revenue',
    icon: DollarSign,
    format: fmt.currency,
    color: '#6366f1',
    bg: 'rgba(99,102,241,0.1)',
  },
  {
    key: 'total_orders',
    label: 'Total Orders',
    icon: ShoppingCart,
    format: fmt.number,
    color: '#22c55e',
    bg: 'rgba(34,197,94,0.1)',
  },
  {
    key: 'avg_order_value',
    label: 'Avg. Order Value',
    icon: TrendingUp,
    format: fmt.currency,
    color: '#f59e0b',
    bg: 'rgba(245,158,11,0.1)',
  },
  {
    key: 'unique_customers',
    label: 'Unique Customers',
    icon: Users,
    format: fmt.number,
    color: '#06b6d4',
    bg: 'rgba(6,182,212,0.1)',
  },
  {
    key: 'top_product',
    label: 'Top Product',
    icon: Package,
    format: (v) => v,
    color: '#a855f7',
    bg: 'rgba(168,85,247,0.1)',
  },
  {
    key: 'top_region',
    label: 'Top Region',
    icon: MapPin,
    format: (v) => v,
    color: '#f43f5e',
    bg: 'rgba(244,63,94,0.1)',
  },
]

function SkeletonCard() {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between mb-4">
        <div className="skeleton w-10 h-10 rounded-lg" />
        <div className="skeleton w-16 h-5 rounded" />
      </div>
      <div className="skeleton w-24 h-7 rounded mb-1" />
      <div className="skeleton w-20 h-4 rounded" />
    </div>
  )
}

export default function KPICards({ kpis, loading }) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {CARDS.map((_, i) => <SkeletonCard key={i} />)}
      </div>
    )
  }

  if (!kpis) return null

  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
      {CARDS.map(({ key, label, icon: Icon, format, color, bg }, i) => {
        const value = kpis[key]
        const isGrowth = key === 'total_revenue' && kpis.revenue_growth != null
        const growth = kpis.revenue_growth

        return (
          <div
            key={key}
            className="card p-5 page-enter"
            style={{ animationDelay: `${i * 60}ms`, animationFillMode: 'backwards' }}
          >
            {/* Icon */}
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center justify-center w-9 h-9 rounded-lg"
                style={{ background: bg }}>
                <Icon size={16} color={color} />
              </div>
              {isGrowth && (
                <span className={growth >= 0 ? 'badge-success' : 'badge-danger'}>
                  {fmt.percent(growth)}
                </span>
              )}
            </div>

            {/* Value */}
            <div className="stat-number text-xl font-semibold truncate"
              style={{ color: 'var(--text-primary)' }}>
              {value != null ? format(value) : '—'}
            </div>

            {/* Label */}
            <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              {label}
            </div>
          </div>
        )
      })}
    </div>
  )
}
