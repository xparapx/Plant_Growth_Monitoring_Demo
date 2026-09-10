import { NavLink } from 'react-router-dom'
import { Moon, Sun } from 'lucide-react'
import { useTheme } from '@/app/theme'
import { ko } from '@/i18n/ko'
import { LiveDot } from '@/components/ui/LiveDot'
import { useSummary } from '@/api/queries'
import { useRunStatus } from '@/hooks/useRunStatus'

const NAV = [
  { to: '/overview', label: ko.nav.overview },
  { to: '/treatment', label: ko.nav.treatment },
  { to: '/growth', label: ko.nav.growth },
  { to: '/camera', label: ko.nav.camera },
  { to: '/system', label: ko.nav.system },
]

/** Mockup header: sunken navy bar, `plantlab°` wordmark, tracked uppercase tabs with an accent underline,
    and the run status ("● 4 nodes · Day 14/42 · 18:04 KST") on the right. */
export function TopBar() {
  const { theme, toggle } = useTheme()
  const { data } = useSummary()
  const run = useRunStatus(data)
  return (
    <header className="sticky top-0 z-30 border-b border-border-soft bg-sunken/92 backdrop-blur supports-[backdrop-filter]:bg-sunken/85">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-4 px-4 md:h-16 md:px-9">
        <NavLink to="/overview" className="flex items-center gap-2 text-ink no-underline" aria-label={ko.app}>
          <Wordmark />
          {data?.capture?.driver === 'fake' && <span className="badge-dummy">FAKE CAM</span>}
        </NavLink>
        <nav aria-label="주 메뉴" className="ml-4 hidden h-full items-center gap-7 md:flex">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} className="nav-item">{n.label}</NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3 md:gap-4">
          <span className="hidden items-center gap-2 whitespace-nowrap text-[11px] font-medium text-muted md:flex" title={run.title}>
            <span className="inline-block h-[7px] w-[7px] rounded-full" style={{ background: run.online > 0 ? 'var(--live)' : 'var(--ink-faint)' }} aria-hidden="true" />
            <span className="num">{run.text}</span>
          </span>
          <LiveDot />
          <button
            type="button"
            onClick={toggle}
            aria-label={ko.theme.toggle}
            title={theme === 'dark' ? ko.theme.light : ko.theme.dark}
            className="grid h-8 w-8 place-items-center rounded-full border border-border-soft text-muted hover:text-ink"
          >
            {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
          </button>
        </div>
      </div>
    </header>
  )
}

export function Wordmark({ size = 18 }: { size?: number }) {
  return (
    <span className="font-semibold leading-none text-ink" style={{ fontSize: size }}>
      {ko.app}<span className="text-accent">°</span>
    </span>
  )
}
