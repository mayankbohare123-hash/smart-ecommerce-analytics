/**
 * api.js
 * ──────
 * Axios base instance for all API calls.
 * The Vite proxy (vite.config.js) forwards /api → http://localhost:8000
 * so no CORS issues during development.
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,          // 30s — training can take a few seconds
  headers: { 'Content-Type': 'application/json' },
})

// ── Response interceptor — normalize errors ──────────────────────────────────
api.interceptors.response.use(
  (response) => response.data,   // unwrap .data automatically
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.response?.data?.error ||
      error.message ||
      'An unexpected error occurred.'
    return Promise.reject(new Error(message))
  }
)

export default api
