import type { ReactNode } from 'react'
import { Toggle } from '@/components/ui/Toggle'

const INPUT = 'num h-10 w-full rounded-md border border-border-soft bg-elev px-2.5 text-[14px] text-ink outline-none focus:border-primary disabled:opacity-60'

export function TextField({ label, value, onChange, placeholder, readOnly, mono = true }: { label: string; value: string; onChange?: (v: string) => void; placeholder?: string; readOnly?: boolean; mono?: boolean }) {
  const id = `tf-${label.replace(/\s+/g, '-')}`
  return (
    <label htmlFor={id} className="flex flex-col gap-1 text-[12px]">
      <span className="label !text-[10px]">{label}</span>
      <input id={id} type="text" value={value} readOnly={readOnly} disabled={readOnly} placeholder={placeholder} onChange={(e) => onChange?.(e.target.value)} className={`${INPUT} ${mono ? '' : 'font-sans'}`} />
    </label>
  )
}

export function SelectField<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: readonly T[]; onChange: (v: T) => void }) {
  const id = `sf-${label.replace(/\s+/g, '-')}`
  return (
    <label htmlFor={id} className="flex flex-col gap-1 text-[12px]">
      <span className="label !text-[10px]">{label}</span>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value as T)} className={INPUT}>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  )
}

export function ToggleField({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex flex-col gap-1 text-[12px]">
      <span className="label !text-[10px]">{label}</span>
      <div className="flex h-10 items-center gap-2">
        <Toggle checked={checked} onChange={onChange} label={label} />
        <span className="num text-[12px] text-muted">{checked ? 'true' : 'false'}</span>
      </div>
    </div>
  )
}

export function Section({ title, children, cols = 4 }: { title: string; children: ReactNode; cols?: 2 | 3 | 4 | 5 }) {
  const grid = { 2: 'sm:grid-cols-2', 3: 'sm:grid-cols-3', 4: 'sm:grid-cols-2 lg:grid-cols-4', 5: 'sm:grid-cols-3 lg:grid-cols-5' }[cols]
  return (
    <fieldset className="rounded-md border border-border-soft p-3">
      <legend className="label px-1 !text-[10px]">{title}</legend>
      <div className={`grid grid-cols-1 gap-3 ${grid}`}>{children}</div>
    </fieldset>
  )
}
