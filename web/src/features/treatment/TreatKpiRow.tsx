import { m } from 'motion/react'
import { useAnalytics } from '@/api/queries'
import type { Summary } from '@/api/types'
import { cardEnter } from '@/components/ui/Card'
import { DummyBadge } from '@/components/ui/DummyBadge'
import { Skeleton } from '@/components/ui/Skeleton'
import { VerdictPill } from '@/components/ui/TreatPill'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { TREAT_LETTER, trtVar } from '@/lib/treat'

/** Mockup 3b top row: MEAN ALIGNMENT · VARIANCE RATIO · 총 급수량 (S … mL / F … mL). */
export function TreatKpiRow({ summary }: { summary: Summary }) {
  const v = summary.validity
  const water = useAnalytics('water')
  const groups = water.data ? Object.keys(water.data.groups) : []
  return (
    <m.div variants={cardEnter} className="grid grid-cols-1 gap-3.5 sm:grid-cols-3 md:col-span-2 xl:col-span-12">
      <Kpi label={ko.treatKpi.mean} dummy={summary.dummy.includes('soil')}>
        {v.enough_groups ? (
          <>
            <Big>{fmtNum(v.dmu, 2)} %p</Big>
            <VerdictPill ok={!!v.aligned} size="lg">{v.aligned ? ko.treatKpi.alignedLt(v.tol_pp) : ko.treatKpi.driftGe(v.tol_pp)}</VerdictPill>
          </>
        ) : <Muted>{ko.check.needBoth}</Muted>}
      </Kpi>
      <Kpi label={ko.treatKpi.ratio} dummy={summary.dummy.includes('soil')}>
        {v.enough_groups ? (
          <>
            <Big>{fmtNum(v.ratio, 2)} ×</Big>
            <VerdictPill ok={false} tone={v.separated ? 'accent' : 'stable'} size="lg">{v.separated ? ko.treatKpi.sepGt(v.sep_ratio) : ko.treatKpi.closeLe(v.sep_ratio)}</VerdictPill>
          </>
        ) : <Muted>{ko.check.needBoth}</Muted>}
      </Kpi>
      <Kpi label={ko.water.totalShort} dummy={summary.dummy.includes('pump')}>
        {water.isPending && <Skeleton className="h-8 w-40" />}
        {water.data && groups.length === 0 && <Muted>{ko.pumpEvents.none}</Muted>}
        {water.data && groups.map((g) => (
          <span key={g} className="num text-[26px] font-semibold leading-none" style={{ color: trtVar(g, 'ink') }}>
            {TREAT_LETTER[g] ?? g[0].toUpperCase()} {fmtNum(water.data!.groups[g].total_ml, 0)} mL
          </span>
        ))}
      </Kpi>
    </m.div>
  )
}

function Kpi({ label, dummy, children }: { label: string; dummy?: boolean; children: React.ReactNode }) {
  return (
    <div className="card px-6 py-5">
      <div className="label flex items-center gap-2 normal-case !tracking-[.12em]">{label}{dummy && <DummyBadge />}</div>
      <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-2">{children}</div>
    </div>
  )
}
const Big = ({ children }: { children: React.ReactNode }) => <span className="num text-[34px] font-semibold leading-none text-ink md:text-[40px]">{children}</span>
const Muted = ({ children }: { children: React.ReactNode }) => <span className="text-[12px] text-muted">{children}</span>
