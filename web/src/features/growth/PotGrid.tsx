import type { UseQueryResult } from '@tanstack/react-query'
import { m } from 'motion/react'
import { useAnalytics, useSoil } from '@/api/queries'
import type { Rgr, SilFrame, Summary } from '@/api/types'
import { cardEnter } from '@/components/ui/Card'
import { DummyBadge } from '@/components/ui/DummyBadge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { TreatPill } from '@/components/ui/TreatPill'
import { useIsMobile } from '@/hooks/useBreakpoint'
import { ko } from '@/i18n/ko'
import { fmtHm, fmtNum } from '@/lib/format'

/** Mockup 3c: one card per pot — canopy projection (latest frame) on a sunken stage, name + treatment pill + area, RGR · soil. */
export function PotGrid({ summary, rgr, mask }: { summary: Summary; rgr: UseQueryResult<Rgr>; mask: boolean }) {
  const sil = useAnalytics('silhouettes')
  const soil = useSoil('auto')
  const mobile = useIsMobile()
  const pots = summary.pots
  const ncol = mobile ? Math.min(summary.ncol, 2) : Math.min(Math.max(summary.ncol, 1), 3)
  const rgrOf = (id: string) => rgr.data?.pots.find((p) => p.pot === id)
  const soilOf = (id: string) => {
    const p = soil.data?.pots.find((x) => x.plant_id === id)
    if (!p) return null
    for (let i = p.pct.length - 1; i >= 0; i--) if (p.pct[i] !== null) return p.pct[i]
    return null
  }
  const maxRgr = rgr.data ? Math.max(...rgr.data.pots.map((p) => p.rgr)) : null
  return (
    <m.div variants={cardEnter} className="md:col-span-2 xl:col-span-12">
      {summary.dummy.includes('growth') && <div className="mb-2"><DummyBadge /></div>}
      {sil.isPending && <Skeleton className="h-56" />}
      {sil.data && pots.length === 0 && <EmptyState title={ko.sawtooth.noPots} compact />}
      {sil.data && pots.length > 0 && (
        <div className="grid gap-3.5" style={{ gridTemplateColumns: `repeat(${ncol}, minmax(0, 1fr))` }}>
          {pots.map((pot) => {
            const s = sil.data!.pots.find((x) => x.plant_id === pot.id)
            const r = rgrOf(pot.id)
            const sp = soilOf(pot.id)
            const best = r && maxRgr !== null && r.rgr === maxRgr && rgr.data!.pots.length > 1
            return (
              <div key={pot.id} className={`card overflow-hidden ${best ? 'outline outline-[1.5px] outline-accent' : ''}`}>
                <Stage frame={s?.new ?? null} lim={s?.lim ?? 1} mask={mask} best={!!best} />
                <div className="px-4 pb-3.5 pt-3">
                  <div className="flex items-baseline gap-2">
                    <span className="num text-[14px] font-semibold text-ink">{pot.id.toUpperCase()}</span>
                    <TreatPill treat={pot.treat} />
                    <span className="num ml-auto whitespace-nowrap text-[15px] font-semibold text-ink md:text-[18px]">{s?.new.area_cm2 !== null && s?.new.area_cm2 !== undefined ? `${fmtNum(s.new.area_cm2, 1)} cm²` : '—'}</span>
                  </div>
                  <div className="num mt-0.5 flex text-[11px] text-muted">
                    <span>{r ? `${ko.pots.rgr(r.rgr)}${best ? ` · ${ko.pots.max}` : ''}` : 'RGR —'}</span>
                    <span className="ml-auto">{sp === null ? 'soil —' : ko.pots.soil(sp)}</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </m.div>
  )
}

function Stage({ frame, lim, mask, best }: { frame: SilFrame | null; lim: number; mask: boolean; best: boolean }) {
  const L = lim || 1
  const pts = frame ? frame.contour.map(([x, y]) => `${x},${y}`).join(' ') : ''
  const phase = frame ? (new Date(frame.ts).getHours() < 12 ? 'DAWN' : 'PM') : ''
  return (
    <div className="relative bg-sunken">
      <svg viewBox={`${-L * 2.1} ${-L} ${L * 4.2} ${L * 2}`} className="block aspect-[380/180] w-full" role="img" aria-label={frame ? `캐노피 투영 ${fmtNum(frame.area_cm2, 1)} cm²` : ko.pots.noFrame}>
        {frame && <polygon points={pts} fill="var(--leaf)" fillOpacity={mask ? 0.16 : 0} stroke="var(--leaf)" strokeWidth={L * 0.012} strokeLinejoin="round" />}
        {frame && best && <polygon points={pts} fill="none" stroke="var(--accent)" strokeWidth={L * 0.012} strokeDasharray={`${L * 0.03} ${L * 0.03}`} strokeLinejoin="round" opacity="0.9" />}
      </svg>
      <span className="num absolute bottom-2 left-3 text-[10px] text-muted">
        {frame ? `${phase} ${fmtHm(frame.ts)} · ${best ? ko.pots.contour : ko.pots.method}` : ko.pots.noFrame}
      </span>
    </div>
  )
}
