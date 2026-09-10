import { Check } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'

export interface Step { id: string; title: string; done?: boolean; active?: boolean; failed?: boolean; skipped?: boolean; hint?: string }

/** Horizontal compact stepper (job progress). */
export function HStepper({ steps }: { steps: Step[] }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-1 gap-y-2" aria-label="진행 단계">
      {steps.map((s, i) => {
        const tone = s.failed ? 'bg-accent text-white' : s.done ? 'bg-stable text-stable-on' : s.active ? 'bg-ink text-bg animate-[pulse-soft_1.2s_ease-in-out_infinite]' : s.skipped ? 'bg-sunken text-faint' : 'bg-sunken text-muted'
        return (
          <li key={s.id} className="flex items-center gap-1">
            <span className={`flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[11px] font-medium ${tone} ${s.skipped ? 'opacity-60 line-through' : ''}`} aria-current={s.active ? 'step' : undefined}>
              {s.done && !s.failed ? <Check size={12} strokeWidth={3} /> : <span className="num">{i + 1}</span>}
              {s.title}
            </span>
            {i < steps.length - 1 && <span className="h-px w-3 bg-border-soft" aria-hidden="true" />}
          </li>
        )
      })}
    </ol>
  )
}

/** Step badge from the mockup: done = stable fill + navy check, active = accent fill + number, pending = outlined number. */
export function StepBadge({ i, done, active, size = 22 }: { i: number; done?: boolean; active?: boolean; size?: number }) {
  const cls = done ? 'bg-stable text-stable-on' : active ? 'bg-accent text-white' : 'border-[1.5px] border-muted text-muted'
  return (
    <span className={`grid flex-none place-items-center rounded-full text-[11px] font-bold ${cls}`} style={{ width: size, height: size }} aria-hidden="true">
      {done ? <Check size={12} strokeWidth={3.2} /> : i + 1}
    </span>
  )
}

/**
 * Vertical stepper (camera setup, mockup 3d): done / pending steps collapse to one row with a value hint,
 * the active step is expanded with an accent outline. Any row can be opened by clicking its header.
 */
export function VStepper({ steps, children }: { steps: Step[]; children: (s: Step, i: number) => ReactNode }) {
  const activeIdx = steps.findIndex((s) => s.active)
  const [open, setOpen] = useState<number | null>(activeIdx)
  useEffect(() => { setOpen(activeIdx) }, [activeIdx])
  return (
    <ol className="flex flex-col gap-3">
      {steps.map((s, i) => {
        const expanded = open === i
        return (
          <li key={s.id} className={`card overflow-hidden rounded-[14px] ${s.active ? 'outline outline-[1.5px] outline-accent' : ''}`}>
            <button
              type="button"
              onClick={() => setOpen(expanded ? null : i)}
              aria-expanded={expanded}
              aria-controls={`step-${s.id}`}
              className="flex w-full items-center gap-2.5 px-4 py-3 text-left"
            >
              <StepBadge i={i} done={s.done} active={s.active} />
              <span className={`min-w-0 truncate text-[12px] ${s.active ? 'font-semibold' : 'font-medium'} text-ink`}>{i + 1} · {s.title}</span>
              <span className="num ml-auto truncate text-[10.5px] text-muted">{s.active ? s.hint ?? '' : s.hint ?? ''}</span>
            </button>
            {expanded && <div id={`step-${s.id}`} className="border-t border-border-soft px-4 py-3">{children(s, i)}</div>}
          </li>
        )
      })}
    </ol>
  )
}
