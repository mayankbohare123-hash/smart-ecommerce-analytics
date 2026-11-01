/** AdminLayout.jsx — shell for every /admin page: its own sidebar + scrolling content area. */
import { Outlet } from 'react-router-dom'
import AdminSidebar from './AdminSidebar'

export default function AdminLayout() {
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-base)' }}>
      <AdminSidebar />
      <main className="flex flex-col flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
