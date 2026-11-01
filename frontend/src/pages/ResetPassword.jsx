/**
 * pages/ResetPassword.jsx — the page the emailed link opens: /reset-password?token=…
 */
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Zap, Lock, Eye, EyeOff, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'
import api from '../services/api'
import { useAuth } from '../context/AuthContext'

export default function ResetPassword() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const navigate = useNavigate()
  const { logout } = useAuth()

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [show, setShow] = useState(false)
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
    if (password !== confirm) { setError("The two passwords don't match."); return }
    setLoading(true)
    try {
      await api.post('/auth/reset-password', { token, password })
      await logout()                      // clear any stale session on this browser
      setDone(true)
    } catch (err) {
      setError(err.message || 'Could not reset your password.')
    } finally {
      setLoading(false)
    }
  }

  const shell = (children) => (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg-base)' }}>
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl" style={{ background: 'var(--accent)' }}>
            <Zap size={20} color="#fff" fill="#fff" />
          </div>
          <span className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>SalesIQ</span>
        </div>
        <div className="rounded-2xl border p-8" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>{children}</div>
      </div>
    </div>
  )

  if (!token) {
    return shell(
      <div className="text-center">
        <AlertCircle size={40} className="mx-auto mb-4" style={{ color: '#f59e0b' }} />
        <h1 className="text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>This link isn&apos;t valid</h1>
        <p className="text-sm mb-5" style={{ color: 'var(--text-secondary)' }}>The reset link is missing its token. Please request a new one.</p>
        <Link to="/forgot-password" className="btn-primary justify-center">Request a new link</Link>
      </div>,
    )
  }

  if (done) {
    return shell(
      <div className="text-center">
        <CheckCircle2 size={40} className="mx-auto mb-4" style={{ color: '#22c55e' }} />
        <h1 className="text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Password updated</h1>
        <p className="text-sm mb-5" style={{ color: 'var(--text-secondary)' }}>
          You&apos;ve been signed out everywhere. Log in with your new password.
        </p>
        <button className="btn-primary justify-center" onClick={() => navigate('/login', { replace: true })}>Go to log in</button>
      </div>,
    )
  }

  return shell(
    <>
      <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--text-primary)' }}>Choose a new password</h1>
      <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>Use at least 8 characters.</p>

      {error && (
        <div className="p-3 rounded-lg mb-4" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)' }}>
          <div className="flex items-start gap-2">
            <AlertCircle size={16} className="mt-0.5 shrink-0" style={{ color: '#f87171' }} />
            <p className="text-sm" style={{ color: '#f87171' }}>{error}</p>
          </div>
          {/invalid or has expired/i.test(error) && (
            <Link to="/forgot-password" className="inline-block text-sm font-medium underline mt-2" style={{ color: '#f87171' }}>
              Request a new link
            </Link>
          )}
        </div>
      )}

      <form onSubmit={submit} className="space-y-4">
        <div>
          <label htmlFor="pw" className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>New password</label>
          <div className="relative">
            <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
            <input id="pw" type={show ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)}
              className="input pl-9 pr-10" autoComplete="new-password" required />
            <button type="button" onClick={() => setShow((v) => !v)} aria-label={show ? 'Hide password' : 'Show password'}
              className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }}>
              {show ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
        </div>
        <div>
          <label htmlFor="pw2" className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>Confirm new password</label>
          <div className="relative">
            <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
            <input id="pw2" type={show ? 'text' : 'password'} value={confirm} onChange={(e) => setConfirm(e.target.value)}
              className="input pl-9" autoComplete="new-password" required />
          </div>
        </div>
        <button type="submit" disabled={loading}
          className="btn-primary w-full justify-center py-2.5 disabled:opacity-60 disabled:cursor-not-allowed">
          {loading && <Loader2 size={15} className="animate-spin" />}
          {loading ? 'Updating…' : 'Update password'}
        </button>
      </form>
    </>,
  )
}
