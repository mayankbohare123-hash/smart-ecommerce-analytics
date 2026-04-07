/**
 * Dashboard.jsx
 * ─────────────
 * Main landing page — shows KPI cards + 4 charts.
 * Prompts user to upload a file if none is selected.
 */
import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Upload, RefreshCw, AlertCircle } from 'lucide-react'
import { useData } from '../context/DataContext'
import KPICards from '../components/KPICards'
import SalesChart from '../components/SalesChart'
import { ProductChart, CategoryChart, RegionChart } from '../components/ProductChart'

function ChartCard({ title, subtitle, children }) {
  return (
    <div className="card p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{title}</h3>
        {subtitle && <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{subtitle}</p>}
      </div>
      {children}
    </div>
  )
}

export default function Dashboard() {
  const {
    selectedFileId, files, analytics, charts,
    loadingAnalytics, error, refreshFiles,
  } = useData()

  useEffect(() => { refreshFiles() }, [])

  // ── No file selected ───────────────────────────────────────────────────────
  if (!selectedFileId) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 gap-6 py-20 mesh-bg page-enter">
        <div className="flex items-center justify-center w-16 h-16 rounded-2xl"
          style={{ background: 'var(--accent-muted)' }}>
          <Upload size={28} style={{ color: 'var(--accent)' }} />
        </div>
        <div className="text-center max-w-sm">
          <h2 className="text-xl font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
            No dataset selected
          </h2>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Upload a CSV sales file to unlock your analytics dashboard, charts, and ML-powered forecasts.
          </p>
        </div>
        <div className="flex gap-3">
          <Link to="/upload" className="btn-primary">
            <Upload size={15} /> Upload CSV
          </Link>
          {files.length > 0 && (
            <p className="text-sm self-center" style={{ color: 'var(--text-muted)' }}>
              or select a file from the sidebar
            </p>
          )}
        </div>
      </div>
    )
  }

  // ── Error state ────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 gap-4 py-20 page-enter">
        <AlertCircle size={32} style={{ color: 'var(--danger)' }} />
        <div className="text-center">
          <h2 className="text-lg font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
            Failed to load analytics
          </h2>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{error}</p>
        </div>
        <button onClick={() => window.location.reload()} className="btn-ghost">
          <RefreshCw size={14} /> Reload
        </button>
      </div>
    )
  }

  return (
    <div className="flex-1 p-6 space-y-6 page-enter overflow-y-auto">

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
            Dashboard
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {analytics
              ? `Showing analytics for dataset #${selectedFileId}`
              : 'Loading analytics…'}
          </p>
        </div>
        {analytics && (
          <Link to="/predictions" className="btn-primary text-sm">
            <span>View Predictions</span>
            <span>→</span>
          </Link>
        )}
      </div>

      {/* ── KPI Cards ───────────────────────────────────────── */}
      <KPICards kpis={analytics?.kpis} loading={loadingAnalytics} />

      {/* ── Charts row 1: Revenue trend + Top products ──────── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <ChartCard
          title="Monthly Revenue Trend"
          subtitle="Revenue ($) and order count over time"
        >
          <SalesChart data={charts?.revenue_trend} loading={loadingAnalytics} />
        </ChartCard>

        <ChartCard
          title="Top Products by Revenue"
          subtitle="Ranked by total net revenue"
        >
          <ProductChart data={charts?.top_products} loading={loadingAnalytics} />
        </ChartCard>
      </div>

      {/* ── Charts row 2: Category + Region ─────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <ChartCard
          title="Revenue by Category"
          subtitle="Share of total revenue per product category"
        >
          <CategoryChart data={charts?.category_pie} loading={loadingAnalytics} />
        </ChartCard>

        <ChartCard
          title="Sales by Region"
          subtitle="Revenue and order count by geographic region"
        >
          <RegionChart data={charts?.region_bar} loading={loadingAnalytics} />
        </ChartCard>
      </div>

      {/* ── Summary text ────────────────────────────────────── */}
      {analytics && (
        <div className="card p-5" style={{ borderColor: 'var(--border)' }}>
          <p className="section-label mb-2">Summary</p>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            {`Dataset covers ${analytics.monthly_sales?.[0]?.month ?? '—'} to ${analytics.monthly_sales?.at(-1)?.month ?? '—'} `}
            {`with ${analytics.kpis?.total_orders?.toLocaleString()} orders generating `}
            {`$${analytics.kpis?.total_revenue?.toLocaleString()} in revenue. `}
            {`Average order value is $${analytics.kpis?.avg_order_value?.toLocaleString()}. `}
            {`Top product: ${analytics.kpis?.top_product}. `}
            {`Strongest region: ${analytics.kpis?.top_region}.`}
          </p>
        </div>
      )}
    </div>
  )
}
