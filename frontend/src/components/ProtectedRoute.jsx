/**
 * components/ProtectedRoute.jsx
 * ──────────────────────────────
 * Wraps any route that requires authentication.
 * Shows a loading spinner while checking the stored token.
 * Redirects to /login if not authenticated, preserving the intended URL.
 */

import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Zap } from 'lucide-react'

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()
  const location = useLocation()

  // Still checking the stored token — show a spinner
  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4"
        style={{ background: 'var(--bg-base)' }}>
        <div className="flex items-center justify-center w-12 h-12 rounded-xl"
          style={{ background: 'var(--accent)' }}>
          <Zap size={24} color="#fff" fill="#fff" />
        </div>
        <div className="flex items-center gap-2" style={{ color: 'var(--text-muted)' }}>
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
          </svg>
          <span className="text-sm">Loading SalesIQ…</span>
        </div>
      </div>
    )
  }

  // Not authenticated — redirect to login, remembering where they were going
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
