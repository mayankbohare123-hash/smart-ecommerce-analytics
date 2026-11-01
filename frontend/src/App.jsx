/**
 * App.jsx — UPDATED with auth routes and ProtectedRoute.
 *
 * Route structure:
 *   /login    → Login page (public)
 *   /signup   → Signup page (public)
 *   /         → Dashboard (protected)
 *   /upload   → Upload (protected)
 *   /analytics→ Analytics (protected)
 *   /predictions → Predictions (protected)
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { DataProvider }    from './context/DataContext'
import { AuthProvider }    from './context/AuthContext'
import ProtectedRoute      from './components/ProtectedRoute'
import Sidebar             from './components/Sidebar'
import Dashboard           from './pages/Dashboard'
import Upload              from './pages/Upload'
import Analytics           from './pages/Analytics'
import Predictions         from './pages/Predictions'
import Login               from './pages/Login'
import Signup              from './pages/Signup'
import Pricing             from './pages/Pricing'
import Billing             from './pages/Billing'
import BillingSuccess      from './pages/BillingSuccess'
import ForgotPassword      from './pages/ForgotPassword'
import ResetPassword       from './pages/ResetPassword'
import AdminRoute          from './components/AdminRoute'
import AdminLayout         from './components/admin/AdminLayout'
import AdminOverview       from './pages/admin/AdminOverview'
import AdminUsers          from './pages/admin/AdminUsers'
import AdminUserDetail     from './pages/admin/AdminUserDetail'
import AdminActivity       from './pages/admin/AdminActivity'

// The main app layout (sidebar + content) — only shown when authenticated
function Layout() {
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-base)' }}>
      <Sidebar />
      <main className="flex flex-col flex-1 overflow-hidden">
        <Routes>
          <Route path="/"            element={<Dashboard />} />
          <Route path="/upload"      element={<Upload />} />
          <Route path="/analytics"   element={<Analytics />} />
          <Route path="/predictions" element={<Predictions />} />
          <Route path="/pricing"         element={<Pricing />} />
          <Route path="/billing"         element={<Billing />} />
          <Route path="/billing/success" element={<BillingSuccess />} />
          <Route path="*"            element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login"  element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password"  element={<ResetPassword />} />

          {/* Founder's admin panel — separate layout, admins only */}
          <Route path="/admin" element={<ProtectedRoute><AdminRoute><AdminLayout /></AdminRoute></ProtectedRoute>}>
            <Route index element={<AdminOverview />} />
            <Route path="users" element={<AdminUsers />} />
            <Route path="users/:id" element={<AdminUserDetail />} />
            <Route path="activity" element={<AdminActivity />} />
          </Route>

          {/* Protected routes — wrapped in DataProvider only after auth */}
          <Route path="/*" element={
            <ProtectedRoute>
              <DataProvider>
                <Layout />
              </DataProvider>
            </ProtectedRoute>
          } />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
