import { NavLink } from 'react-router-dom'
import { Moon, Sun } from 'lucide-react'
import { useTheme } from '@/app/theme'
import { ko } from '@/i18n/ko'
import { LiveDot } from '@/components/ui/LiveDot'
import { useSummary } from '@/api/queries'
import { fmtTimeLocal } from '@/lib/format'

const NAV = [
  { to: '/overview', label: ko.nav.overview },
  { to: '/treatment', label: ko.nav.treatment },
  { to: '/growth', label: ko.nav.growth },
  { to: '/camera', label: ko.nav.camera },
  { to: '/system', label: ko.nav.system },
]

export function TopBar() {
  const { theme, toggle } = useTheme()
  const { data, dataUpdatedAt } = useSummary()
  return (
    <header className="sticky top-0 z-30 border-b border-border-soft bg-elev/85 backdrop-blur supports-[backdrop-filter]:bg-elev/70">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-4 px-4 md:px-6">
        <NavLink to="/overview" className="flex items-center gap-2.5 text-ink no-underline">
          <BrandMark />
          <span className="text-[15px] font-800 tracking-tight" style={{ fontWeight: 800 }}>{ko.app}</span>
          {data?.capture?.driver === 'fake' && <span className="badge-dummy">FAKE CAM</span>}
        </NavLink>
        <nav aria-label="주 메뉴" className="ml-4 hidden items-center gap-1 md:flex">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-[13px] font-semibold no-underline transition-colors duration-[var(--dur-fast)] ` +
                (isActive ? 'bg-primary text-primary-ink' : 'text-muted hover:bg-sunken hover:text-ink')
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          {dataUpdatedAt > 0 && <span className="num hidden text-[11px] text-muted sm:inline">{ko.updated(fmtTimeLocal(new Date(dataUpdatedAt)))}</span>}
          <LiveDot />
          <button
            type="button"
            onClick={toggle}
            aria-label={ko.theme.toggle}
            title={theme === 'dark' ? ko.theme.light : ko.theme.dark}
            className="grid h-9 w-9 place-items-center rounded-md border border-border-soft bg-elev text-muted hover:text-ink"
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </div>
    </header>
  )
}

function BrandMark() {
  return (
    <svg width="26" height="26" viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="14" fill="var(--ink)" />
      <path d="M32 50c0-14 6-24 18-30-2 14-8 24-18 30z" fill="var(--bg)" />
      <path d="M32 50c0-10-5-18-16-24 2 12 6 20 16 24z" fill="var(--primary)" />
      <circle cx="32" cy="50" r="3.2" fill="var(--accent)" />
    </svg>
  )
}
