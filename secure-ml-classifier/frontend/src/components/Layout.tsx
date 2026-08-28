import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../lib/auth'

const links = [
  { to: '/', label: 'Overview', end: true },
  { to: '/datasets', label: 'Datasets' },
  { to: '/runs', label: 'Models' },
  { to: '/account', label: 'Account' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const nav = user?.role === 'admin' ? [...links, { to: '/admin', label: 'Security' }] : links

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 border-b border-edge bg-surface/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-3">
          <div className="flex items-center gap-8">
            <span className="flex items-center gap-2 font-semibold">
              <span className="text-lg">🛡️</span> SecureML
            </span>
            <nav className="flex items-center gap-1">
              {nav.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.end}
                  className={({ isActive }) =>
                    `rounded-lg px-3 py-1.5 text-sm transition ${
                      isActive ? 'bg-accent/15 text-accent' : 'text-slate-300 hover:bg-white/5'
                    }`
                  }
                >
                  {link.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-slate-400 sm:inline">{user?.email}</span>
            <span className="badge bg-sky-500/15 text-sky-300">{user?.role}</span>
            <button className="btn-ghost py-1" onClick={() => void logout()} type="button">
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
