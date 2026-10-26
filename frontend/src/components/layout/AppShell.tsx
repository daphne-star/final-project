import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  Building2,
  LayoutDashboard,
  Menu,
  ScrollText,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react'

import { useHealth } from '@/api/agents'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

const NAV: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/board', label: 'My Board', icon: Users },
  { to: '/decisions', label: 'Decisions', icon: ScrollText },
  { to: '/company', label: 'Company', icon: Building2 },
]

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="relative z-10 flex min-h-dvh flex-col lg:flex-row">
      {/* Mobile bar */}
      <header className="flex items-center justify-between border-b border-line bg-surface/80 px-4 py-3 backdrop-blur lg:hidden">
        <Wordmark />
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMobileOpen((v) => !v)}
          aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'}
          aria-expanded={mobileOpen}
        >
          {mobileOpen ? <X /> : <Menu />}
        </Button>
      </header>

      <aside
        className={cn(
          'border-line bg-surface/60 lg:flex lg:w-60 lg:shrink-0 lg:flex-col lg:border-r',
          mobileOpen ? 'block border-b lg:border-b-0' : 'hidden',
        )}
      >
        <div className="hidden px-5 py-6 lg:block">
          <Wordmark />
        </div>

        <nav className="flex flex-col gap-1 p-3 lg:px-3 lg:py-0">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-surface-raised text-ink'
                    : 'text-ink-muted hover:bg-surface-raised/60 hover:text-ink',
                )
              }
            >
              <Icon className="size-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto hidden p-4 lg:block">
          <BackendStatus />
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <Outlet />
      </main>
    </div>
  )
}

function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <span
        aria-hidden
        className="grid size-7 place-items-center rounded-md bg-accent/20 text-accent-soft"
      >
        <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M4 20V8a8 8 0 0 1 16 0v12l-3-2-2.5 2L12 18l-2.5 2L7 18Z" strokeLinejoin="round" />
          <circle cx="9.5" cy="11" r="1.2" fill="currentColor" stroke="none" />
          <circle cx="14.5" cy="11" r="1.2" fill="currentColor" stroke="none" />
        </svg>
      </span>
      <span className="font-display text-lg leading-none tracking-tight">Ghost Board</span>
    </div>
  )
}

function BackendStatus() {
  const { data, isError } = useHealth()
  const ok = data?.status === 'ok'
  const label = isError
    ? 'API unreachable'
    : data
      ? `API ${data.status} · DB ${data.database.split(':')[0]}`
      : 'Checking…'

  return (
    <div className="flex items-center gap-2 rounded-md border border-line px-3 py-2 text-xs text-ink-muted">
      <span
        aria-hidden
        className={cn(
          'size-1.5 shrink-0 rounded-full',
          isError ? 'bg-critical' : ok ? 'bg-positive' : 'bg-caution',
        )}
      />
      <span className="truncate">{label}</span>
    </div>
  )
}
