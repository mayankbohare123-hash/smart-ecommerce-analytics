/** pages/admin/AdminActivity.jsx — audit trail of everything admins did to customer accounts. */
import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { getAdminActivity } from '../../services/adminApi'
import Banner from '../../components/Banner'
import { formatDateTime } from '../../utils/format'
import { Pill } from './AdminUsers'

const ACTIONS = {
  suspend:     ['Suspended', 'rgba(245,158,11,0.14)', '#fbbf24'],
  restore:     ['Restored', 'rgba(34,197,94,0.12)', '#4ade80'],
  set_plan:    ['Plan changed', 'rgba(14,165,233,0.14)', '#38bdf8'],
  delete_user: ['Deleted', 'rgba(239,68,68,0.14)', '#f87171'],
}

export default function AdminActivity() {
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { getAdminActivity({ page, limit: 30 }).then(setData).catch((e) => setError(e.message)) }, [page])

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8 page-enter">
      <div className="max-w-5xl mx-auto space-y-5">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Activity log</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>Every admin action on a customer account. Entries are kept even after a customer is deleted.</p>
        </div>
        {error && <Banner tone="error">{error}</Banner>}
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs" style={{ color: 'var(--text-muted)' }}>
                {['When', 'Admin', 'Action', 'Customer', 'Details'].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {data?.entries.map((e) => {
                const [label, bg, color] = ACTIONS[e.action] || [e.action, 'rgba(255,255,255,0.06)', '#8892a4']
                return (
                  <tr key={e.id} className="border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
                    <td className="px-4 py-3 whitespace-nowrap">{formatDateTime(e.at)}</td>
                    <td className="px-4 py-3">{e.admin}</td>
                    <td className="px-4 py-3"><Pill bg={bg} color={color}>{label}</Pill></td>
                    <td className="px-4 py-3">{e.target}</td>
                    <td className="px-4 py-3" style={{ color: 'var(--text-muted)' }}>{e.detail || '—'}</td>
                  </tr>
                )
              })}
              {data && data.entries.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-10 text-center" style={{ color: 'var(--text-muted)' }}>Nothing yet — actions you take on customers will appear here.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {data && data.pages > 1 && (
          <div className="flex items-center justify-between text-sm" style={{ color: 'var(--text-muted)' }}>
            <span>Page {data.page} of {data.pages}</span>
            <div className="flex gap-2">
              <button className="btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}><ChevronLeft size={15} /> Prev</button>
              <button className="btn-ghost" disabled={page >= data.pages} onClick={() => setPage((p) => p + 1)}>Next <ChevronRight size={15} /></button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
