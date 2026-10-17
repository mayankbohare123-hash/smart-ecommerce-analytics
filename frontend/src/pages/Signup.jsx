/**
 * pages/Signup.jsx
 * ────────────────
 * Account creation page matching the dark SalesIQ theme.
 */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Zap, User, Mail, Lock, Eye, EyeOff, AlertCircle, CheckCircle } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function Signup() {
  const [name,     setName]     = useState('')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [showPwd,  setShowPwd]  = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')

  const { signup } = useAuth()
  const navigate   = useNavigate()

  const pwdStrength = password.length === 0 ? null : password.length < 8 ? 'weak' : password.length < 12 ? 'good' : 'strong'
  const pwdColor    = { weak: '#ef4444', good: '#f59e0b', strong: '#22c55e' }
  const pwdWidth    = { weak: '33%', good: '66%', strong: '100%' }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!name.trim())      { setError('Please enter your name.'); return }
    if (!email.trim())     { setError('Please enter your email.'); return }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }

    setLoading(true)
    try {
      await signup(name.trim(), email.trim(), password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Signup failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8"
      style={{ background: 'var(--bg-base)' }}>

      <div className="w-full max-w-md">

        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl"
            style={{ background: 'var(--accent)' }}>
            <Zap size={20} color="#fff" fill="#fff" />
          </div>
          <span className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>SalesIQ</span>
        </div>

        {/* Card */}
        <div className="rounded-2xl border p-8"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>

          <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--text-primary)' }}>
            Create your account
          </h1>
          <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
            Start with a free plan — no credit card required
          </p>

          {/* Free plan features */}
          <div className="flex flex-wrap gap-3 mb-6">
            {['1 dataset free', 'All charts', 'ML predictions'].map(f => (
              <span key={f} className="flex items-center gap-1 text-xs"
                style={{ color: 'var(--text-secondary)' }}>
                <CheckCircle size={12} style={{ color: 'var(--accent)' }} />
                {f}
              </span>
            ))}
          </div>

          {/* Error alert */}
          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg mb-4"
              style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)' }}>
              <AlertCircle size={16} className="mt-0.5 shrink-0" style={{ color: '#f87171' }} />
              <p className="text-sm" style={{ color: '#f87171' }}>{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>
                Full name
              </label>
              <div className="relative">
                <User size={15} className="absolute left-3 top-1/2 -translate-y-1/2"
                  style={{ color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Mayank Bohare"
                  className="input pl-9"
                  autoComplete="name"
                  required
                />
              </div>
            </div>

            {/* Email */}
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>
                Email address
              </label>
              <div className="relative">
                <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2"
                  style={{ color: 'var(--text-muted)' }} />
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="input pl-9"
                  autoComplete="email"
                  required
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>
                Password
              </label>
              <div className="relative">
                <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2"
                  style={{ color: 'var(--text-muted)' }} />
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
                  className="input pl-9 pr-10"
                  autoComplete="new-password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2"
                  style={{ color: 'var(--text-muted)' }}>
                  {showPwd ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>

              {/* Password strength bar */}
              {pwdStrength && (
                <div className="mt-2">
                  <div className="h-1 rounded-full" style={{ background: 'var(--bg-elevated)' }}>
                    <div className="h-1 rounded-full transition-all duration-300"
                      style={{ width: pwdWidth[pwdStrength], background: pwdColor[pwdStrength] }} />
                  </div>
                  <p className="text-xs mt-1 capitalize" style={{ color: pwdColor[pwdStrength] }}>
                    {pwdStrength} password
                  </p>
                </div>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full justify-center py-2.5 mt-2 disabled:opacity-60 disabled:cursor-not-allowed">
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Creating account…
                </span>
              ) : 'Create free account'}
            </button>
          </form>

          {/* Footer */}
          <p className="text-center text-sm mt-6" style={{ color: 'var(--text-muted)' }}>
            Already have an account?{' '}
            <Link to="/login" className="font-medium hover:underline" style={{ color: 'var(--accent)' }}>
              Log in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
