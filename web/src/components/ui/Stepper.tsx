import { Check } from 'lucide-react'
import type { ReactNode } from 'react'

export interface Step { id: string; title: string; done?: boolean; active?: boolean; failed?: boolean; skipped?: boolean; hint?: string }

/** Horizontal compact stepper (job progress). */
export function HStepper({ steps }: { steps: Step[] }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-1 gap-y-2" aria-label="진행 단계">
      {steps.map((s, i) => {
        const tone = s.failed ? 'bg-bad text-white' : s.done ? 'bg-ok text-white' : s.active ? 'bg-primary text-primary-ink animate-[pulse-soft_1.2s_ease-in-out_infinite]' : s.skipped ? 'bg-sunken text-faint' : 'bg-sunken text-muted'
        return (
          <li key={s.id} className="flex items-center gap-1">
            <span className={`flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[11.5px] font-semibold ${tone} ${s.skipped ? 'opacity-60 line-through' : ''}`} aria-current={s.active ? 'step' : undefined}>
              {s.done && !s.failed ? <Check size={12} /> : <span className="num">{i + 1}</span>}
              {s.title}
            </span>
            {i < steps.length - 1 && <span className="h-px w-3 bg-border-soft" aria-hidden="true" />}
          </li>
        )
      })}
    </ol>
  )
}

/** Vertical stepper with expandable bodies (camera setup). */
export function VStepper({ steps, children }: { steps: Step[]; children: (s: Step, i: number) => ReactNode }) {
  return (
    <ol className="flex flex-col gap-3">
      {steps.map((s, i) => (
        <li key={s.id} className={`card overflow-hidden ${s.active ? 'ring-2 ring-primary/40' : ''}`}>
          <div className="flex items-center gap-3 px-4 py-3">
            <span className={`grid h-7 w-7 flex-none place-items-center rounded-full text-[12px] font-bold ${s.done ? 'bg-ok text-white' : 'bg-sunken text-muted'}`}>
              {s.done ? <Check size={14} /> : i + 1}
            </span>
            <div className="min-w-0">
              <div className="text-[14px] font-bold">{s.title}</div>
              {s.hint && <div className="text-[11.5px] text-muted">{s.hint}</div>}
            </div>
          </div>
          <div className="border-t border-border-soft px-4 py-3">{children(s, i)}</div>
        </li>
      ))}
    </ol>
  )
}
