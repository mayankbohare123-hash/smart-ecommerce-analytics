/**
 * Upload.jsx
 * ──────────
 * File upload page with upload zone + uploaded files list.
 */
import { useEffect } from 'react'
import { Trash2, Eye, CheckCircle2, Clock } from 'lucide-react'
import FileUpload from '../components/FileUpload'
import { useData } from '../context/DataContext'
import { deleteFile } from '../services/analyticsApi'

export default function Upload() {
  const { files, refreshFiles, selectFile, selectedFileId } = useData()

  useEffect(() => { refreshFiles() }, [])

  const handleDelete = async (id) => {
    if (!confirm('Delete this file and all its data?')) return
    try {
      await deleteFile(id)
      await refreshFiles()
    } catch (e) {
      alert(e.message)
    }
  }

  return (
    <div className="flex-1 p-6 space-y-6 page-enter overflow-y-auto">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Upload Data</h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          Upload a CSV file with sales data to start analysing
        </p>
      </div>

      {/* Required columns hint */}
      <div className="card p-4">
        <p className="section-label mb-2">Required columns</p>
        <div className="flex flex-wrap gap-2">
          {[
            ['order_date', 'date / sale_date', 'required'],
            ['net_revenue', 'revenue / total / sales', 'required'],
            ['product', 'product_name / item', 'optional'],
            ['category', 'product_category', 'optional'],
            ['region', 'area / zone / territory', 'optional'],
            ['quantity', 'qty / units_sold', 'optional'],
            ['customer_id', 'user_id / client_id', 'optional'],
          ].map(([name, aliases, req]) => (
            <div key={name} className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
              <span className="font-mono font-medium" style={{ color: req === 'required' ? '#818cf8' : 'var(--text-secondary)' }}>
                {name}
              </span>
              <span style={{ color: 'var(--text-muted)' }}>· {aliases}</span>
              <span className={req === 'required' ? 'badge-accent' : 'badge-gray'}>{req}</span>
            </div>
          ))}
        </div>
      </div>

      <FileUpload onSuccess={() => refreshFiles()} />

      {/* Uploaded files list */}
      {files.length > 0 && (
        <div className="card">
          <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Uploaded Files ({files.length})
            </h3>
          </div>
          <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
            {files.map(file => (
              <div key={file.id} className="flex items-center gap-4 px-5 py-3.5">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg shrink-0"
                  style={{ background: file.status === 'processed' ? 'rgba(34,197,94,0.12)' : 'var(--bg-elevated)' }}>
                  {file.status === 'processed'
                    ? <CheckCircle2 size={15} color="#4ade80" />
                    : <Clock size={15} style={{ color: 'var(--text-muted)' }} />
                  }
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                    {file.original_name}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                    {file.row_count?.toLocaleString()} rows ·
                    ID #{file.id} ·
                    {new Date(file.uploaded_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className={file.status === 'processed' ? 'badge-success' : 'badge-warning'}>
                    {file.status}
                  </span>
                  <button
                    onClick={() => selectFile(file.id)}
                    className="btn-ghost py-1 px-2 text-xs"
                    style={{ color: selectedFileId === file.id ? '#818cf8' : undefined }}
                  >
                    <Eye size={13} />
                    {selectedFileId === file.id ? 'Active' : 'Select'}
                  </button>
                  <button
                    onClick={() => handleDelete(file.id)}
                    className="btn-ghost py-1 px-2 text-xs"
                    style={{ color: 'var(--danger)' }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
