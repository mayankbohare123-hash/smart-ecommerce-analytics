/**
 * Sidebar.jsx
 * ───────────
 * Left navigation sidebar with:
 *   - Logo / brand mark
 *   - File selector (active upload)
 *   - Nav links with icons
 *   - Mini stats footer
 */
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Upload, BarChart3, TrendingUp,
  ChevronDown, Database, Circle, Zap
} from 'lucide-react'
import { useData } from '../context/DataContext'
import { useState } from 'react'

const NAV = [
  { to: '/',            icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/upload',      icon: Upload,          label: 'Upload Data' },
  { to: '/analytics',   icon: BarChart3,        label: 'Analytics' },
  { to: '/predictions', icon: TrendingUp,       label: 'Predictions' },
]

export default function Sidebar() {
  const { files, selectedFileId, selectFile } = useData()
  const [fileOpen, setFileOpen] = useState(false)
  const navigate = useNavigate()

  const activeFile = files.find(f => f.id === selectedFileId)

  const handleFileSelect = (file) => {
    selectFile(file.id)
    setFileOpen(false)
    navigate('/')
  }

  return (
    <aside className="flex flex-col w-60 min-h-screen border-r shrink-0"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>

      {/* ── Brand ─────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-5 py-5 border-b"
        style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-center w-8 h-8 rounded-lg"
          style={{ background: 'var(--accent)' }}>
          <Zap size={16} color="#fff" fill="#fff" />
        </div>
        <div>
          <div className="text-sm font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>
            SalesIQ
          </div>
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Analytics Platform</div>
        </div>
      </div>

      {/* ── Active file selector ───────────────────────────────── */}
      <div className="px-3 pt-4 pb-2">
        <p className="section-label mb-2 px-2">Active Dataset</p>
        <button
          onClick={() => setFileOpen(o => !o)}
          className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            color: activeFile ? 'var(--text-primary)' : 'var(--text-muted)',
          }}
        >
          <span className="flex items-center gap-2 truncate">
            <Database size={13} />
            <span className="truncate">
              {activeFile ? activeFile.original_name : 'No file selected'}
            </span>
          </span>
          <ChevronDown size={13} className={`shrink-0 transition-transform ${fileOpen ? 'rotate-180' : ''}`} />
        </button>

        {/* Dropdown */}
        {fileOpen && files.length > 0 && (
          <div className="mt-1 rounded-lg overflow-hidden shadow-xl"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
            {files.map(file => (
              <button
                key={file.id}
                onClick={() => handleFileSelect(file)}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors hover:bg-white/5"
                style={{ color: file.id === selectedFileId ? '#818cf8' : 'var(--text-secondary)' }}
              >
                <Circle size={6} fill={file.id === selectedFileId ? '#6366f1' : 'transparent'}
                  stroke={file.id === selectedFileId ? '#6366f1' : 'currentColor'} />
                <span className="truncate">{file.original_name}</span>
              </button>
            ))}
          </div>
        )}

        {fileOpen && files.length === 0 && (
          <div className="mt-1 px-3 py-2 rounded-lg text-xs"
            style={{ color: 'var(--text-muted)', background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
            No files uploaded yet
          </div>
        )}
      </div>

      {/* ── Navigation ────────────────────────────────────────── */}
      <nav className="flex-1 px-3 py-2 space-y-0.5">
        <p className="section-label mb-2 px-2 pt-2">Navigation</p>
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 ${
                isActive ? 'nav-active' : 'hover:bg-white/5'
              }`
            }
            style={({ isActive }) => ({
              color: isActive ? '#818cf8' : 'var(--text-secondary)',
            })}
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* ── Footer ────────────────────────────────────────────── */}
      <div className="px-4 py-4 border-t" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-between text-xs" style={{ color: 'var(--text-muted)' }}>
          <span>{files.length} dataset{files.length !== 1 ? 's' : ''}</span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse-slow inline-block" />
            API online
          </span>
        </div>
      </div>
    </aside>
  )
}
