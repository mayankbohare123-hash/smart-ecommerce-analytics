/**
 * pages/ForgotPassword.jsx — asks for an email and requests a reset link.
 * The confirmation is identical for registered and unknown emails on purpose.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Zap, Mail, AlertCircle, CheckCircle2, ArrowLeft, Loader2 } from 'lucide-react'
import api from '../services/api'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (!email.trim()) { setError('Please enter your email address.'); return }
    setLoading(true)
    try {
      await api.post('/auth/forgot-password', { email: email.trim() })
      setSent(true)
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg-base)' }}>
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl" style={{ background: 'var(--accent)' }}>
            <Zap size={20} color="#fff" fill="#fff" />
          </div>
          <span className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>SalesIQ</span>
        </div>

        <div className="rounded-2xl border p-8" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          {sent ? (
            <div className="text-center">
              <CheckCircle2 size={40} className="mx-auto mb-4" style={{ color: '#22c55e' }} />
              <h1 className="text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Check your email</h1>
              <p className="text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>
                If an account exists for <strong>{email.trim()}</strong>, we&apos;ve sent a link to reset the password.
              </p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                The link works once and expires in 1 hour. Check your spam folder if it doesn&apos;t arrive.
              </p>
            </div>
          ) : (
            <>
              <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--text-primary)' }}>Forgot your password?</h1>
              <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
                Enter your email and we&apos;ll send you a link to choose a new one.
              </p>

              {error && (
                <div className="flex items-start gap-2 p-3 rounded-lg mb-4"
                  style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)' }}>
                  <AlertCircle size={16} className="mt-0.5 shrink-0" style={{ color: '#f87171' }} />
                  <p className="text-sm" style={{ color: '#f87171' }}>{error}</p>
                </div>
              )}

              <form onSubmit={submit} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>Email address</label>
                  <div className="relative">
                    <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
                    <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com" className="input pl-9" autoComplete="email" required />
                  </div>
                </div>
                <button type="submit" disabled={loading}
                  className="btn-primary w-full justify-center py-2.5 disabled:opacity-60 disabled:cursor-not-allowed">
                  {loading && <Loader2 size={15} className="animate-spin" />}
                  {loading ? 'Sending…' : 'Send reset link'}
                </button>
              </form>
            </>
          )}

          <p className="text-center text-sm mt-6">
            <Link to="/login" className="inline-flex items-center gap-1 font-medium hover:underline" style={{ color: 'var(--accent)' }}>
              <ArrowLeft size={14} /> Back to log in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
