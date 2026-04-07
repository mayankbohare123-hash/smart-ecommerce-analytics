/**
 * FileUpload.jsx
 * ──────────────
 * Drag-and-drop CSV uploader with:
 *   - Visual drag states
 *   - File type + size validation
 *   - Progress indicator during upload
 *   - Success / error feedback
 *   - Column mapping preview on success
 */
import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, File, CheckCircle, XCircle, Loader2, CloudUpload } from 'lucide-react'
import { uploadFile } from '../services/analyticsApi'
import { useData } from '../context/DataContext'

const MAX_MB = 10
const ACCEPTED = { 'text/csv': ['.csv'], 'application/vnd.ms-excel': ['.csv', '.xlsx'] }

export default function FileUpload({ onSuccess }) {
  const { refreshFiles, selectFile } = useData()
  const [status, setStatus]   = useState('idle')  // idle | uploading | success | error
  const [result, setResult]   = useState(null)
  const [errMsg, setErrMsg]   = useState('')
  const [progress, setProgress] = useState(0)

  const onDrop = useCallback(async (accepted, rejected) => {
    if (rejected.length > 0) {
      setStatus('error')
      setErrMsg('Invalid file. Please upload a CSV file under 10 MB.')
      return
    }
    if (accepted.length === 0) return

    const file = accepted[0]
    if (file.size > MAX_MB * 1024 * 1024) {
      setStatus('error')
      setErrMsg(`File is too large (${(file.size/1024/1024).toFixed(1)} MB). Max is ${MAX_MB} MB.`)
      return
    }

    setStatus('uploading')
    setProgress(0)
    setResult(null)
    setErrMsg('')

    // Simulate progress while uploading
    const ticker = setInterval(() => {
      setProgress(p => Math.min(p + Math.random() * 15, 85))
    }, 200)

    try {
      const formData = new FormData()
      formData.append('file', file)
      const data = await uploadFile(formData)

      clearInterval(ticker)
      setProgress(100)
      setStatus('success')
      setResult(data)

      // Refresh file list and auto-select the new file
      await refreshFiles()
      await selectFile(data.file_id)

      if (onSuccess) onSuccess(data)
    } catch (e) {
      clearInterval(ticker)
      setStatus('error')
      setErrMsg(e.message)
    }
  }, [refreshFiles, selectFile, onSuccess])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxFiles: 1,
    disabled: status === 'uploading',
  })

  const reset = () => { setStatus('idle'); setResult(null); setErrMsg('') }

  return (
    <div className="space-y-4">
      {/* ── Drop zone ───────────────────────────────────────── */}
      <div
        {...getRootProps()}
        className={`relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed 
          p-10 text-center cursor-pointer transition-all duration-200
          ${isDragActive ? 'dropzone-active' : ''}
          ${status === 'uploading' ? 'opacity-60 cursor-not-allowed' : 'hover:border-indigo-500/50 hover:bg-white/[0.02]'}`}
        style={{ borderColor: isDragActive ? 'var(--accent)' : 'var(--border)' }}
      >
        <input {...getInputProps()} />

        {/* Icon */}
        <div className="flex items-center justify-center w-14 h-14 rounded-full"
          style={{ background: isDragActive ? 'var(--accent-muted)' : 'var(--bg-elevated)' }}>
          {status === 'uploading'
            ? <Loader2 size={24} className="animate-spin" style={{ color: 'var(--accent)' }} />
            : <CloudUpload size={24} style={{ color: isDragActive ? 'var(--accent)' : 'var(--text-muted)' }} />
          }
        </div>

        {status === 'uploading' ? (
          <div className="space-y-2">
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              Uploading and processing…
            </p>
            {/* Progress bar */}
            <div className="w-48 h-1.5 rounded-full mx-auto" style={{ background: 'var(--bg-hover)' }}>
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{ width: `${progress}%`, background: 'var(--accent)' }}
              />
            </div>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{Math.round(progress)}%</p>
          </div>
        ) : (
          <>
            <div>
              <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                {isDragActive ? 'Drop your CSV here' : 'Drag & drop your CSV file here'}
              </p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                or click to browse · CSV or Excel · max {MAX_MB} MB
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap justify-center">
              {['order_date', 'net_revenue', 'product', 'category', 'region'].map(col => (
                <span key={col} className="badge-gray text-xs font-mono">{col}</span>
              ))}
            </div>
          </>
        )}
      </div>

      {/* ── Success state ───────────────────────────────────── */}
      {status === 'success' && result && (
        <div className="card p-5 page-enter" style={{ borderColor: 'rgba(34,197,94,0.3)' }}>
          <div className="flex items-start gap-3">
            <CheckCircle size={20} className="shrink-0 mt-0.5" style={{ color: 'var(--success)' }} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Upload successful
              </p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                {result.message}
              </p>

              {/* Stats row */}
              <div className="flex flex-wrap gap-3 mt-3">
                {[
                  ['Rows',    result.row_count.toLocaleString()],
                  ['Columns', result.column_count],
                  ['File ID', `#${result.file_id}`],
                ].map(([label, val]) => (
                  <div key={label} className="px-3 py-1.5 rounded-lg"
                    style={{ background: 'var(--bg-elevated)' }}>
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}: </span>
                    <span className="text-xs font-medium stat-number" style={{ color: 'var(--text-primary)' }}>{val}</span>
                  </div>
                ))}
              </div>

              {/* Detected columns */}
              <div className="mt-3">
                <p className="text-xs mb-1.5" style={{ color: 'var(--text-muted)' }}>Detected columns:</p>
                <div className="flex flex-wrap gap-1.5">
                  {result.columns.map(col => (
                    <span key={col} className="badge-accent font-mono text-xs">{col}</span>
                  ))}
                </div>
              </div>

              <button onClick={reset} className="btn-ghost mt-4 text-xs py-1.5">
                Upload another file
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Error state ─────────────────────────────────────── */}
      {status === 'error' && (
        <div className="card p-4 page-enter" style={{ borderColor: 'rgba(239,68,68,0.3)' }}>
          <div className="flex items-start gap-3">
            <XCircle size={18} className="shrink-0 mt-0.5" style={{ color: 'var(--danger)' }} />
            <div>
              <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Upload failed</p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{errMsg}</p>
              <button onClick={reset} className="btn-ghost mt-3 text-xs py-1.5">Try again</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
