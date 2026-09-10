import type { ReactNode } from 'react'

export function Segmented<T extends string>({ options, value, onChange, size = 'md', ariaLabel }: { options: { value: T; label: ReactNode; disabled?: boolean }[]; value: T; onChange: (v: T) => void; size?: 'sm' | 'md'; ariaLabel?: string }) {
  return (
    <div role="radiogroup" aria-label={ariaLabel} className="inline-flex rounded-md border border-border-soft bg-sunken p-0.5">
      {options.map((o) => {
        const on = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={on}
            disabled={o.disabled}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => {
              if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
              const i = options.findIndex((x) => x.value === value)
              const j = (i + (e.key === 'ArrowRight' ? 1 : -1) + options.length) % options.length
              onChange(options[j].value)
            }}
            className={`rounded-[5px] font-semibold transition-colors ${size === 'sm' ? 'h-7 px-2.5 text-[12px]' : 'h-8 px-3 text-[13px]'} ${on ? 'bg-elev text-ink shadow-1' : 'text-muted hover:text-ink'} disabled:opacity-40`}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
