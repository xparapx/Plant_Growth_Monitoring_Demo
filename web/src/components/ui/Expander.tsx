import { ChevronRight } from 'lucide-react'
import { useState, type ReactNode } from 'react'

/** <details>-based; body renders only after the first open (lazy). */
export function Expander({ summary, children, defaultOpen = false, onOpen }: { summary: ReactNode; children: ReactNode; defaultOpen?: boolean; onOpen?: () => void }) {
  const [opened, setOpened] = useState(defaultOpen)
  return (
    <details
      open={defaultOpen}
      onToggle={(e) => { if ((e.target as HTMLDetailsElement).open) { setOpened(true); onOpen?.() } }}
      className="group rounded-md border border-border-soft bg-elev"
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-[13px] font-semibold text-muted [&::-webkit-details-marker]:hidden">
        <ChevronRight size={15} className="transition-transform group-open:rotate-90" aria-hidden="true" />
        {summary}
      </summary>
      <div className="border-t border-border-soft px-4 py-3">{opened ? children : null}</div>
    </details>
  )
}
