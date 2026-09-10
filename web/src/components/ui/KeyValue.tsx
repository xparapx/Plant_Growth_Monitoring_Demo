import type { ReactNode } from 'react'

export function KeyValue({ items, cols = 2 }: { items: { k: string; v: ReactNode; note?: string }[]; cols?: 1 | 2 | 3 }) {
  const grid = cols === 1 ? 'grid-cols-1' : cols === 3 ? 'grid-cols-2 md:grid-cols-3' : 'grid-cols-2'
  return (
    <dl className={`grid gap-x-4 gap-y-2 ${grid}`}>
      {items.map((it) => (
        <div key={it.k} className="min-w-0">
          <dt className="label !text-[9.5px]">{it.k}</dt>
          <dd className="num truncate text-[13px] text-ink" title={typeof it.v === 'string' ? it.v : undefined}>{it.v}</dd>
          {it.note && <dd className="text-[11px] text-muted">{it.note}</dd>}
        </div>
      ))}
    </dl>
  )
}
