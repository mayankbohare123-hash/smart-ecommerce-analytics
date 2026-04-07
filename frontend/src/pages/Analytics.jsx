/**
 * Analytics.jsx
 * ─────────────
 * Detailed analytics page — tables + charts for deep-dive analysis.
 */
import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useData } from '../context/DataContext'
import { ProductChart, CategoryChart, RegionChart } from '../components/ProductChart'
import SalesChart from '../components/SalesChart'

function NoFile() {
  return (
    <div className="flex flex-col items-center justify-center flex-1 gap-4 py-20">
      <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
        No dataset selected. <Link to="/upload" className="underline" style={{ color: 'var(--accent)' }}>Upload a file</Link> or select one from the sidebar.
      </p>
    </div>
  )
}

function Table({ columns, rows, loading }) {
  if (loading) return <div className="skeleton h-48 rounded-xl w-full" />
  if (!rows?.length) return null
  return (
    <div className="overflow-x-auto rounded-xl" style={{ border: '1px solid var(--border)' }}>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr style={{ background: 'var(--bg-elevated)' }}>
            {columns.map(c => (
              <th key={c.key} className="px-4 py-3 text-left font-medium text-xs uppercase tracking-wide"
                style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="transition-colors hover:bg-white/[0.02]"
              style={{ borderBottom: i < rows.length - 1 ? '1px solid var(--border)' : 'none' }}>
              {columns.map(c => (
                <td key={c.key} className="px-4 py-3 stat-number text-xs"
                  style={{ color: 'var(--text-secondary)' }}>
                  {c.format ? c.format(row[c.key]) : row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const fmtCurrency = v => `$${Number(v).toLocaleString()}`
const fmtPct      = v => `${v}%`
const fmtNum      = v => Number(v).toLocaleString()

export default function Analytics() {
  const { selectedFileId, analytics, charts, loadingAnalytics, refreshFiles } = useData()
  useEffect(() => { refreshFiles() }, [])
  if (!selectedFileId) return <NoFile />

  return (
    <div className="flex-1 p-6 space-y-6 page-enter overflow-y-auto">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Analytics</h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          Deep-dive into your sales data
        </p>
      </div>

      {/* Monthly trend */}
      <div className="card p-5">
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Monthly Revenue Trend</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Revenue and orders over time</p>
        <SalesChart data={charts?.revenue_trend} loading={loadingAnalytics} />
      </div>

      {/* Top products table + chart */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <div className="card p-5">
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Top Products</h3>
          <Table
            loading={loadingAnalytics}
            columns={[
              { key: 'rank',       label: '#' },
              { key: 'product',    label: 'Product' },
              { key: 'revenue',    label: 'Revenue',    format: fmtCurrency },
              { key: 'units_sold', label: 'Units Sold', format: fmtNum },
            ]}
            rows={analytics?.top_products}
          />
        </div>
        <div className="card p-5">
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Top Products Chart</h3>
          <ProductChart data={charts?.top_products} loading={loadingAnalytics} />
        </div>
      </div>

      {/* Region + Category side by side */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <div className="card p-5">
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Regional Breakdown</h3>
          <Table
            loading={loadingAnalytics}
            columns={[
              { key: 'region',     label: 'Region' },
              { key: 'revenue',    label: 'Revenue',    format: fmtCurrency },
              { key: 'orders',     label: 'Orders',     format: fmtNum },
              { key: 'percentage', label: 'Share',      format: fmtPct },
            ]}
            rows={analytics?.region_sales}
          />
          <div className="mt-4">
            <RegionChart data={charts?.region_bar} loading={loadingAnalytics} />
          </div>
        </div>

        <div className="card p-5">
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Category Breakdown</h3>
          <Table
            loading={loadingAnalytics}
            columns={[
              { key: 'category',   label: 'Category' },
              { key: 'revenue',    label: 'Revenue',    format: fmtCurrency },
              { key: 'units_sold', label: 'Units Sold', format: fmtNum },
            ]}
            rows={analytics?.category_sales}
          />
          <div className="mt-4">
            <CategoryChart data={charts?.category_pie} loading={loadingAnalytics} />
          </div>
        </div>
      </div>
    </div>
  )
}
