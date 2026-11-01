/**
 * AdminSidebar.jsx — navigation for the founder's panel.
 * Amber accents (customers see cyan) so you always know which side you're on.
 */
import { NavLink, Link, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Users, ScrollText, ShieldCheck, ArrowLeftRight, LogOut } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

const NAV = [
  { to: '/admin',          icon: LayoutDashboard, label: 'Overview', end: true },
  { to: '/admin/users',    icon: Users,           label: 'Customers' },
  { to: '/admin/activity', icon: ScrollText,      label: 'Activity log' },
]

export default function AdminSidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <aside className="flex flex-col w-60 min-h-screen border-r shrink-0"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="flex items-center gap-3 px-5 py-5 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-center w-8 h-8 rounded-lg" style={{ background: '#d97706' }}>
          <ShieldCheck size={16} color="#fff" />
        </div>
        <div>
          <div className="text-sm font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>SalesIQ</div>
          <div className="text-xs font-semibold tracking-wider" style={{ color: '#fbbf24' }}>ADMIN PANEL</div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5">
        <p className="section-label mb-2 px-2">Manage</p>
        {NAV.map(({ to, icon: Icon, label, end }) => (
          <NavLink key={to} to={to} end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 ${isActive ? '' : 'hover:bg-white/5'}`}
            style={({ isActive }) => ({
              color: isActive ? '#fbbf24' : 'var(--text-secondary)',
              background: isActive ? 'rgba(245,158,11,0.12)' : undefined,
            })}>
            <Icon size={16} /> {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-3 border-t space-y-2" style={{ borderColor: 'var(--border)' }}>
        <Link to="/" className="flex items-center gap-2 px-2 py-2 rounded-lg text-xs font-medium hover:bg-white/5"
          style={{ color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
          <ArrowLeftRight size={13} /> Switch to customer view
        </Link>
        <div className="flex items-center justify-between px-1">
          <span className="text-xs truncate" style={{ color: 'var(--text-muted)' }} title={user?.email}>{user?.email}</span>
          <button title="Log out" className="p-1.5 rounded-md hover:bg-white/10" style={{ color: 'var(--text-muted)' }}
            onClick={async () => { await logout(); navigate('/login', { replace: true }) }}>
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  )
}
