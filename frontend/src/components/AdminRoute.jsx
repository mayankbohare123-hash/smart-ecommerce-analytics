/**
 * AdminRoute.jsx — keeps customers out of /admin in the UI.
 * (Cosmetic only: the API itself returns 403 to non-admins, which is the real protection.)
 */
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function AdminRoute({ children }) {
  const { user } = useAuth()
  if (user?.role !== 'admin') return <Navigate to="/" replace />
  return children
}
