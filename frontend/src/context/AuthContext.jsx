/**
 * context/AuthContext.jsx
 * ─────────────────────────
 * Global auth state — wraps the entire app so any component can access:
 *   const { user, isAuthenticated, login, signup, logout, loading } = useAuth()
 *
 * Tokens are stored in localStorage for persistent login across page refreshes.
 * On every app load, /api/auth/me is called to validate the stored token.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const AuthContext = createContext(null)

// ── Axios instance used only for auth calls (no circular dependency) ──────────
const authApi = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Token helpers ─────────────────────────────────────────────────────────────
const TOKEN_KEY   = 'salesiq_access_token'
const REFRESH_KEY = 'salesiq_refresh_token'

export const getStoredToken   = () => localStorage.getItem(TOKEN_KEY)
export const getRefreshToken  = () => localStorage.getItem(REFRESH_KEY)

const storeTokens = (access, refresh) => {
  localStorage.setItem(TOKEN_KEY,   access)
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
}

const clearTokens = () => {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
}


// ── Provider ──────────────────────────────────────────────────────────────────
export function AuthProvider({ children }) {
  const [user,    setUser]    = useState(null)
  const [loading, setLoading] = useState(true)   // true while checking stored token

  // Check if the stored token is still valid on mount
  useEffect(() => {
    const token = getStoredToken()
    if (!token) {
      setLoading(false)
      return
    }
    authApi
      .get('/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(res => setUser(res.data.user))
      .catch(() => clearTokens())
      .finally(() => setLoading(false))
  }, [])

  // ── Auth actions ───────────────────────────────────────────────────────────

  const login = useCallback(async (email, password) => {
    const res = await authApi.post('/auth/login', { email, password })
    const { access_token, refresh_token, user: userData } = res.data
    storeTokens(access_token, refresh_token)
    setUser(userData)
    return userData
  }, [])

  const signup = useCallback(async (name, email, password) => {
    const res = await authApi.post('/auth/signup', { name, email, password })
    const { access_token, refresh_token, user: userData } = res.data
    storeTokens(access_token, refresh_token)
    setUser(userData)
    return userData
  }, [])

  const logout = useCallback(async () => {
    const token = getStoredToken()
    if (token) {
      authApi
        .post('/auth/logout', {}, { headers: { Authorization: `Bearer ${token}` } })
        .catch(() => {})  // ignore errors on logout
    }
    clearTokens()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated: !!user, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// ── Hook ──────────────────────────────────────────────────────────────────────
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
