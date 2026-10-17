/**
 * Sidebar.jsx — UPDATED with user info + logout button.
 *
 * New additions:
 *  - Shows logged-in user's name and plan badge at the bottom
 *  - Logout button that calls AuthContext.logout()
 *  - Plan badge: FREE (gray) / STARTER (blue) / PRO (gold)
 */

import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Upload, BarChart3, TrendingUp,
  ChevronDown, Database, Circle, Zap, Github, LogOut,
  Crown, User,
} from 'lucide-react'
import { useData }  from '../context/DataContext'
import { useAuth }  from '../context/AuthContext'
import { useState } from 'react'

const BRAND = {
  name:    'SalesIQ',
  tagline: 'Analytics Platform',
}

const AUTHOR = {
  name:      'Mayank Bohare',
  githubUrl: 'https://github.com/mayankbohare123-hash',
}

const NAV = [
  { to: '/',            icon: LayoutDashboard, label: 'Dashboard'   },
  { to: '/upload',      icon: Upload,          label: 'Upload Data' },
  { to: '/analytics',   icon: BarChart3,        label: 'Analytics'  },
  { to: '/predictions', icon: TrendingUp,       label: 'Predictions'},
]

// Plan badge styles
const PLAN_BADGE = {
  free:    { label: 'FREE',    bg: 'rgba(255,255,255,0.06)', color: '#6b7280' },
  starter: { label: 'STARTER', bg: 'rgba(99,102,241,0.15)', color: '#818cf8' },
  pro:     { label: 'PRO',     bg: 'rgba(245,158,11,0.15)', color: '#fbbf24' },
}

export default function Sidebar() {
  const { files, selectedFileId, selectFile } = useData()
  const { user, logout }                       = useAuth()
  const [fileOpen,    setFileOpen]    = useState(false)
  const [loggingOut,  setLoggingOut]  = useState(false)
  const navigate = useNavigate()

  const activeFile = files.find(f => f.id === selectedFileId)

  const handleFileSelect = (file) => {
    selectFile(file.id)
    setFileOpen(false)
    navigate('/')
  }

  const handleLogout = async () => {
    setLoggingOut(true)
    await logout()
    navigate('/login', { replace: true })
  }

  const plan  = user?.plan || 'free'
  const badge = PLAN_BADGE[plan] || PLAN_BADGE.free

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
            {BRAND.name}
          </div>
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{BRAND.tagline}</div>
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
          }}>
          <span className="flex items-center gap-2 truncate">
            <Database size={13} />
            <span className="truncate">
              {activeFile ? activeFile.original_name : 'No file selected'}
            </span>
          </span>
          <ChevronDown size={13} className={`shrink-0 transition-transform ${fileOpen ? 'rotate-180' : ''}`} />
        </button>

        {fileOpen && files.length > 0 && (
          <div className="mt-1 rounded-lg overflow-hidden shadow-xl"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
            {files.map(file => (
              <button
                key={file.id}
                onClick={() => handleFileSelect(file)}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors hover:bg-white/5"
                style={{ color: file.id === selectedFileId ? '#818cf8' : 'var(--text-secondary)' }}>
                <Circle size={6}
                  fill={file.id === selectedFileId ? '#6366f1' : 'transparent'}
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
            })}>
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* ── User info + Logout (NEW) ───────────────────────────── */}
      {user && (
        <div className="px-3 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2.5 px-2 py-2 rounded-lg mb-1"
            style={{ background: 'var(--bg-elevated)' }}>
            <div className="flex items-center justify-center w-7 h-7 rounded-full shrink-0"
              style={{ background: 'var(--accent-muted)' }}>
              <User size={13} style={{ color: 'var(--accent)' }} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                {user.name || user.email}
              </p>
              <span className="inline-block text-xs font-semibold px-1.5 py-0.5 rounded mt-0.5"
                style={{ background: badge.bg, color: badge.color, fontSize: '9px', letterSpacing: '0.05em' }}>
                {badge.label}
                {plan === 'pro' && <Crown size={8} className="inline ml-0.5 mb-0.5" />}
              </span>
            </div>
            <button
              onClick={handleLogout}
              disabled={loggingOut}
              title="Log out"
              className="shrink-0 p-1.5 rounded-md transition-colors hover:bg-white/10 disabled:opacity-50"
              style={{ color: 'var(--text-muted)' }}>
              <LogOut size={14} />
            </button>
          </div>

          {/* Dataset count + GitHub */}
          <div className="flex items-center justify-between px-1 mt-1">
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {files.length} dataset{files.length !== 1 ? 's' : ''}
            </span>
            <a href={AUTHOR.githubUrl} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs hover:underline"
              style={{ color: 'var(--text-muted)' }}>
              <Github size={11} />
              {AUTHOR.name}
            </a>
          </div>
        </div>
      )}
    </aside>
  )
}
