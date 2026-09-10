import type { ReactNode } from 'react'

export function EmptyState({ title, hint, action, compact }: { title: string; hint?: ReactNode; action?: ReactNode; compact?: boolean }) {
  return (
    <div className={`flex flex-col items-center justify-center rounded-md border border-dashed border-border-soft text-center ${compact ? 'gap-1 px-3 py-4' : 'gap-2 px-4 py-8'}`}>
      <PotGlyph />
      <div className="text-[13px] font-semibold text-muted">{title}</div>
      {hint && <div className="max-w-md text-[12px] text-faint">{hint}</div>}
      {action}
    </div>
  )
}

function PotGlyph() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--ink-faint)" strokeWidth="1.6" aria-hidden="true">
      <path d="M5 10h14l-1.4 9.2a2 2 0 0 1-2 1.8H8.4a2 2 0 0 1-2-1.8L5 10Z" />
      <path d="M12 10V6m0 0c-1.8-2.2-4.2-2.6-6-1.8 1.2 2.4 3.6 3.2 6 1.8Zm0 0c1.8-2.2 4.2-2.6 6-1.8-1.2 2.4-3.6 3.2-6 1.8Z" />
    </svg>
  )
}
