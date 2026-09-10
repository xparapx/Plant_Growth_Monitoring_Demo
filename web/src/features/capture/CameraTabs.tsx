import { Link, useLocation } from 'react-router-dom'
import { cs } from './strings'

const TABS = [
  { to: '/camera', label: cs.tabs.capture },
  { to: '/camera/setup', label: cs.tabs.setup },
] as const

/** Segmented-style link pair shared by /camera and /camera/setup. */
export function CameraTabs() {
  const { pathname } = useLocation()
  return (
    <nav aria-label="카메라 페이지" className="inline-flex rounded-full border border-border-soft bg-sunken p-0.5">
      {TABS.map((t) => {
        const on = pathname.replace(/\/$/, '') === t.to
        return (
          <Link
            key={t.to}
            to={t.to}
            aria-current={on ? 'page' : undefined}
            className={`inline-flex h-9 items-center rounded-full px-3.5 text-[12px] font-medium no-underline transition-colors md:h-8 ${on ? 'bg-ink text-bg' : 'text-muted hover:text-ink'}`}
          >
            {t.label}
          </Link>
        )
      })}
    </nav>
  )
}
