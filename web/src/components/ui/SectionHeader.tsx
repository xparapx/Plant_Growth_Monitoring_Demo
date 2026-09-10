import type { ReactNode } from 'react'
import { DummyBadge } from './DummyBadge'

export function SectionHeader({ title, sub, dummy, actions, id }: { title: string; sub?: ReactNode; dummy?: boolean; actions?: ReactNode; id?: string }) {
  return (
    <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
      <div>
        <h2 id={id} className="label flex items-center gap-2">
          {title}
          {dummy && <DummyBadge />}
        </h2>
        {sub && <p className="mt-1 text-[12px] text-muted">{sub}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
