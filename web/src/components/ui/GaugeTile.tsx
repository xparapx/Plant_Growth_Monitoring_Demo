import { useCountUp } from '@/hooks/useCountUp'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'

export interface GaugeTileProps {
  label: string
  value: number | null | undefined
  unit?: string
  digits?: number
  /** Gauge range [min, max] and the optimal band [lo, hi] used for the OPTIMAL / LOW / HIGH caption. */
  range: [number, number]
  optimal: [number, number]
  rangeLabel: string
  color: string
  missing?: boolean
  delta?: number | null
}

const CX = 60, CY = 60, R = 44
const ang = (f: number) => Math.PI * (1 - Math.min(1, Math.max(0, f)))
const pt = (f: number, r = R) => [CX + r * Math.cos(ang(f)), CY - r * Math.sin(ang(f))] as const

/** Semi-circular needle gauge from the mockup (viewBox 0 0 120 68; arc M16 60 A44 44 0 0 1 104 60). */
export function GaugeTile({ label, value, unit, digits = 1, range, optimal, rangeLabel, color, missing, delta }: GaugeTileProps) {
  const shown = useCountUp(missing ? null : value ?? null)
  const has = !missing && value !== null && value !== undefined
  const f = has ? (value - range[0]) / (range[1] - range[0]) : 0
  const fs = has && shown !== null ? (shown - range[0]) / (range[1] - range[0]) : 0
  const [ax, ay] = pt(f)
  const [nx, ny] = pt(fs, R - 5)
  const large = 0                                   // a semicircle never needs the large-arc flag
  const status = !has ? ko.env.status.missing : value < optimal[0] ? ko.env.status.low : value > optimal[1] ? ko.env.status.high : ko.env.status.optimal
  const tone = !has ? 'var(--ink-faint)' : color
  return (
    <div className="card flex min-w-0 flex-col items-center px-4 pb-3 pt-4">
      <div className="label flex w-full justify-between !tracking-[.1em]">
        <span className="truncate">{label}</span>
        <span className="num">{rangeLabel}</span>
      </div>
      <svg viewBox="0 0 120 68" className="mt-2 w-full max-w-[160px]" role="img" aria-label={`${label} ${has ? fmtNum(value, digits) + (unit ?? '') : ko.common.sensorMissing} · ${status}`}>
        <path d="M16 60 A44 44 0 0 1 104 60" fill="none" stroke="rgba(242,242,242,.14)" strokeWidth="7" strokeLinecap="round" className="[html[data-theme=light]_&]:stroke-[rgba(23,48,70,.12)]" />
        {has && f > 0.005 && (
          <path d={`M16 60 A44 44 0 ${large} 1 ${ax.toFixed(1)} ${ay.toFixed(1)}`} fill="none" stroke={tone} strokeWidth="7" strokeLinecap="round" style={{ transition: 'd var(--dur-slow) var(--ease-out)' }} />
        )}
        <line x1={CX} y1={CY} x2={nx.toFixed(1)} y2={ny.toFixed(1)} stroke="var(--ink)" strokeWidth="2.5" strokeLinecap="round" opacity={has ? 1 : 0.35} />
        <circle cx={CX} cy={CY} r="4.5" fill="var(--ink)" opacity={has ? 1 : 0.35} />
      </svg>
      <div className={`num mt-0.5 text-[29px] font-semibold leading-tight ${has ? 'text-ink' : 'text-faint'}`}>
        {has && shown !== null ? fmtNum(shown, digits, { group: false }) : ko.common.dash}
        {has && unit && <span className="ml-1 text-[13px] font-medium text-muted">{unit}</span>}
      </div>
      <div className="mt-0.5 text-[10.5px] font-medium tracking-[.08em]" style={{ color: tone }}>{status}</div>
      {delta !== undefined && has && (
        <div className="num mt-0.5 text-[10.5px] text-muted" title={ko.env.delta1d}>
          {delta === null ? '' : `${fmtNum(delta, digits, { sign: true })} · 1d`}
        </div>
      )}
    </div>
  )
}
