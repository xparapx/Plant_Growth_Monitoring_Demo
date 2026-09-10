import type { Summary, Validity } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { trtVar } from '@/lib/treat'

export function ValidityCard({ summary }: { summary: Summary }) {
  const v = summary.validity
  return (
    <Card className="md:col-span-2 xl:col-span-12">
      <SectionHeader title={ko.validity.title} dummy={summary.dummy.includes('soil')} sub="보고서의 첫 번째 표 — 결과 그래프보다 먼저." />
      {!v.enough_groups ? (
        <EmptyState title={ko.validity.needBoth} compact />
      ) : (
        <div className="grid gap-4 md:grid-cols-[1.4fr_1fr]">
          <div>
            <Metric label={ko.validity.mean} value={`${fmtNum(v.dmu, 2)} %p`} verdict={v.aligned ? ko.validity.aligned : ko.validity.drift} ok={!!v.aligned} />
            <MeanAlignStrip v={v} />
          </div>
          <div>
            <Metric label={ko.validity.var} value={`${fmtNum(v.ratio, 2)} ×`} verdict={v.separated ? ko.validity.separated : ko.validity.tooClose} ok={!!v.separated} />
            <SigmaBars v={v} />
          </div>
        </div>
      )}
    </Card>
  )
}

function Metric({ label, value, verdict, ok }: { label: string; value: string; verdict: string; ok: boolean }) {
  return (
    <div className="mb-2">
      <div className="label">{label}</div>
      <div className="mt-1 flex items-baseline gap-3">
        <span className="num text-[26px] font-bold leading-none">{value}</span>
        <span className={`rounded-sm px-2 py-0.5 text-[11px] font-extrabold tracking-wider ${ok ? 'bg-ok-soft text-ok-ink' : 'bg-bad-soft text-bad-ink'}`}>{verdict}</span>
      </div>
    </div>
  )
}

/** Number line: green ±TOL/2 band around μ_stable, two labelled dots. */
function MeanAlignStrip({ v }: { v: Validity }) {
  const mu = v.mu, W = 600, H = 72
  const vals = Object.values(mu)
  const lo = Math.min(...vals) - 5, hi = Math.max(...vals) + 5
  const x = (val: number) => ((val - lo) / (hi - lo)) * (W - 40) + 20
  const s = mu.stable, f = mu.fluct
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block h-[72px] w-full" role="img" aria-label={`평균 정렬: stable ${fmtNum(s, 1)}%, fluct ${fmtNum(f, 1)}%`}>
      <rect x={x(s - v.tol_pp / 2)} y={H / 2 - 12} width={Math.max(2, x(s + v.tol_pp / 2) - x(s - v.tol_pp / 2))} height={24} fill="var(--ok)" opacity="0.18" rx="3" />
      <line x1={20} y1={H / 2} x2={W - 20} y2={H / 2} stroke="var(--border)" strokeWidth="1.5" />
      {([['stable', s], ['fluct', f]] as const).map(([t, val]) => (
        <g key={t}>
          <circle cx={x(val)} cy={H / 2} r="8" fill={trtVar(t, 'fill')} stroke={trtVar(t, 'ink')} strokeWidth="2" />
          <text x={x(val)} y={H / 2 - 16} textAnchor="middle" fontSize="12" fontWeight="700" fill={trtVar(t, 'ink')} fontFamily="var(--font-num)">
            {t[0].toUpperCase()} {fmtNum(val, 1)}
          </text>
        </g>
      ))}
      {[lo + 5, hi - 5].map((tick) => (
        <text key={tick} x={x(tick)} y={H - 6} textAnchor="middle" fontSize="10" fill="var(--ink-muted)" fontFamily="var(--font-num)">{fmtNum(tick, 0)}%</text>
      ))}
    </svg>
  )
}

/** Two horizontal σ bars. */
function SigmaBars({ v }: { v: Validity }) {
  const W = 400, rowH = 26, pad = 8
  const groups = Object.keys(v.sd)
  const max = Math.max(...groups.map((g) => v.sd[g])) || 1
  const H = groups.length * (rowH + pad) + pad
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" style={{ height: H }} role="img" aria-label={groups.map((g) => `${g} σ ${fmtNum(v.sd[g], 2)}`).join(', ')}>
      {groups.map((g, i) => {
        const y = pad + i * (rowH + pad)
        const w = (v.sd[g] / max) * (W - 120)
        return (
          <g key={g}>
            <text x={0} y={y + rowH / 2 + 4} fontSize="11" fontWeight="700" fill={trtVar(g, 'ink')}>{g[0].toUpperCase()}</text>
            <rect x={20} y={y} width={w} height={rowH} rx="4" fill={trtVar(g, 'fill')} stroke={trtVar(g, 'ink')} strokeWidth="1.5" />
            <text x={20 + w + 8} y={y + rowH / 2 + 4} fontSize="11" fill="var(--ink)" fontFamily="var(--font-num)">σ {fmtNum(v.sd[g], 2)} · n={v.n[g]}</text>
          </g>
        )
      })}
    </svg>
  )
}
