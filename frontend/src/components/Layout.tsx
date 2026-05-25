import { NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Upload, LogOut, Leaf } from 'lucide-react'
import { auth } from '../api/endpoints'

export function Layout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()

  const handleLogout = async () => {
    await auth.logout().catch(() => {})
    localStorage.removeItem('token')
    navigate('/login')
  }

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive ? 'bg-green-700 text-white' : 'text-green-100 hover:bg-green-700 hover:text-white'
    }`

  return (
    <div className="min-h-screen flex">
      <aside className="w-56 bg-green-800 flex flex-col">
        <div className="flex items-center gap-2 px-4 py-5 border-b border-green-700">
          <Leaf className="h-6 w-6 text-green-300" />
          <span className="text-white font-semibold text-lg">Breathe ESG</span>
        </div>
        <nav className="flex-1 px-2 py-4 space-y-1">
          <NavLink to="/" end className={linkClass}>
            <LayoutDashboard className="h-4 w-4" />
            Dashboard
          </NavLink>
          <NavLink to="/batches" className={linkClass}>
            <Upload className="h-4 w-4" />
            Data Uploads
          </NavLink>
        </nav>
        <div className="px-2 py-4 border-t border-green-700">
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm font-medium text-green-100 hover:bg-green-700 hover:text-white transition-colors"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 bg-gray-50 overflow-auto">
        {children}
      </main>
    </div>
  )
}
