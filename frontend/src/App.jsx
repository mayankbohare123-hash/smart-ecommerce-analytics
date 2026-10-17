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
