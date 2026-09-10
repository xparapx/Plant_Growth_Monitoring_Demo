import { NavLink, useLocation } from 'react-router-dom'
import { Camera, FlaskConical, LayoutDashboard, Settings2, Sprout } from 'lucide-react'
import { ko } from '@/i18n/ko'

const TABS = [
  { to: '/overview', label: ko.nav.overview, Icon: LayoutDashboard },
  { to: '/treatment', label: ko.nav.treatment, Icon: FlaskConical },
  { to: '/growth', label: ko.nav.growth, Icon: Sprout },
  { to: '/camera', label: ko.nav.camera, Icon: Camera },
  { to: '/system', label: ko.nav.system, Icon: Settings2 },
]

export function BottomTabBar() {
  const { pathname } = useLocation()
  return (
    <nav
      aria-label="하단 탭"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border-soft bg-sunken/95 backdrop-blur md:hidden"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      <ul className="grid grid-cols-5">
        {TABS.map(({ to, label, Icon }) => {
          const active = pathname.startsWith(to)
          return (
            <li key={to}>
              <NavLink
                to={to}
                aria-current={active ? 'page' : undefined}
                className={`relative flex h-14 flex-col items-center justify-center gap-1 text-[9.5px] font-medium uppercase tracking-[.12em] no-underline transition-colors ${active ? 'text-ink' : 'text-muted'}`}
              >
                <Icon size={19} strokeWidth={active ? 2.2 : 1.7} />
                {label}
                {active && <span className="absolute left-1/2 top-0 h-[2px] w-8 -translate-x-1/2 rounded-b bg-accent" aria-hidden="true" />}
              </NavLink>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
