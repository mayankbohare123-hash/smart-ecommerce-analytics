/**
 * App.jsx
 * ───────
 * Root component — sets up React Router, the DataProvider,
 * and the persistent sidebar + main content layout.
 */
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { DataProvider } from './context/DataContext'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import Analytics from './pages/Analytics'
import Predictions from './pages/Predictions'

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
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <DataProvider>
        <Layout />
      </DataProvider>
    </BrowserRouter>
  )
}
