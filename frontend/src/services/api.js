/**
 * services/api.js — UPDATED with JWT auth interceptors.
 *
 * Every request now automatically attaches:
 *   Authorization: Bearer <access_token>
 *
 * On 401 responses, the user is redirected to /login.
 * On token expiry, a refresh is attempted once before redirecting.
 */

import axios from 'axios'
import { getStoredToken, getRefreshToken } from '../context/AuthContext'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Request interceptor — attach Bearer token ─────────────────────────────────
api.interceptors.request.use(
  (config) => {
    const token = getStoredToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ── Response interceptor — handle auth errors + normalize errors ──────────────
let isRefreshing = false

api.interceptors.response.use(
  (response) => response.data,   // unwrap .data automatically

  async (error) => {
    const status = error.response?.status

    // Try refresh once on 401
    if (status === 401 && !isRefreshing) {
      const refreshToken = getRefreshToken()
      if (refreshToken) {
        isRefreshing = true
        try {
          const res = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
          const newToken = res.data.access_token
          localStorage.setItem('salesiq_access_token', newToken)

          // Retry the original request with the new token
          error.config.headers.Authorization = `Bearer ${newToken}`
          isRefreshing = false
          return api(error.config)
        } catch {
          isRefreshing = false
        }
      }
      // Refresh failed or no refresh token — go to login
      localStorage.removeItem('salesiq_access_token')
      localStorage.removeItem('salesiq_refresh_token')
      window.location.href = '/login'
      return Promise.reject(new Error('Session expired. Please log in again.'))
    }

    // Normalize error message for all other errors
    const message =
      error.response?.data?.detail ||
      error.response?.data?.error ||
      error.message ||
      'An unexpected error occurred.'

    return Promise.reject(new Error(message))
  }
)

export default api
