import type { InputHTMLAttributes } from 'react'

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'value'> {
  label: string
  value: number | ''
  onChange: (v: number | '') => void
  unit?: string
}

export function NumberField({ label, value, onChange, unit, className = '', id, ...rest }: Props) {
  const fid = id ?? `nf-${label.replace(/\s+/g, '-')}`
  return (
    <label htmlFor={fid} className={`flex flex-col gap-1 text-[12px] ${className}`}>
      <span className="label !text-[10px]">{label}</span>
      <span className="flex items-center gap-1.5">
        <input
          id={fid}
          type="number"
          inputMode="decimal"
          value={value}
          onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
          className="num h-10 w-full rounded-md border border-border-soft bg-elev px-2.5 text-[14px] text-ink outline-none focus:border-primary"
          {...rest}
        />
        {unit && <span className="text-muted">{unit}</span>}
      </span>
    </label>
  )
}
