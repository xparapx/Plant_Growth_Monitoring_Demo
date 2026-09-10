import { useCountUp } from '@/hooks/useCountUp'
import { fmtNum } from '@/lib/format'
import { ko } from '@/i18n/ko'
import { Sparkline } from './Sparkline'

export interface KpiTileProps {
  label: string
  value: number | null | undefined
  unit?: string
  digits?: number
  delta?: number | null
  deltaLabel?: string
  deltaTone?: 'ok' | 'bad' | 'muted'
  spark?: (number | null)[]
  color?: string
  missing?: boolean
  size?: 'md' | 'lg'
  sub?: string
  group?: boolean
}

export function KpiTile({ label, value, unit, digits = 1, delta, deltaLabel, deltaTone = 'muted', spark, color, missing, size = 'md', sub, group = true }: KpiTileProps) {
  const shown = useCountUp(missing ? null : value ?? null)
  const toneCls = deltaTone === 'ok' ? 'text-ok-ink' : deltaTone === 'bad' ? 'text-bad-ink' : 'text-muted'
  return (
    <div className="card flex min-w-0 flex-col p-3.5 md:p-4">
      <div className="label truncate">{label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className={`num font-bold leading-none ${size === 'lg' ? 'text-[30px]' : 'text-[24px]'} ${missing ? 'text-faint' : 'text-ink'}`}>
          {missing || shown === null ? ko.common.dash : fmtNum(shown, digits, { group })}
        </span>
        {unit && !missing && <span className="text-[12px] text-muted">{unit}</span>}
      </div>
      <div className={`num mt-0.5 min-h-[16px] text-[11.5px] ${missing ? 'text-bad-ink' : toneCls}`}>
        {missing ? ko.common.sensorMissing : deltaLabel ?? (delta !== null && delta !== undefined ? `${fmtNum(delta, digits, { sign: true })} · ${ko.env.delta1d}` : sub ?? '')}
      </div>
      {spark && (
        <div className="mt-2">
          <Sparkline data={spark} color={missing ? 'var(--ink-faint)' : color ?? 'var(--primary)'} flat={missing} />
        </div>
      )}
    </div>
  )
}
