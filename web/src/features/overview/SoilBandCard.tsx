import { useMemo } from 'react'
import { useSoil } from '@/api/queries'
import type { SoilSeries, Summary } from '@/api/types'
import { ChartFrame } from '@/charts/ChartFrame'
import { groupMeanOption } from '@/charts/options/soilBand'
import { Card } from '@/components/ui/Card'
import { DummyBadge } from '@/components/ui/DummyBadge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { useIsMobile } from '@/hooks/useBreakpoint'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { trtVar } from '@/lib/treat'

/** Mockup 3a "토양수분 — 처리 밴드": group-mean trajectories over 7 d with the two bands. */
export function SoilBandCard({ summary }: { summary: Summary }) {
  const mobile = useIsMobile()
  const q = useSoil('auto')
  const groups = Object.keys(summary.groups)
  const option = useMemo(() => (q.data && groups.length ? groupMeanOption(q.data, summary.groups) : null), [q.data, summary.groups, groups.length])
  const centre = centreLabel(q.data)
  return (
    <Card className="md:col-span-2 xl:col-span-8" padded={false}>
      <div className="flex flex-wrap items-baseline gap-x-3.5 gap-y-1 px-5 pt-4">
        <span className="card-title">{ko.soilBand.title}</span>
        {groups.map((g) => (
          <span key={g} className="text-[11px] font-medium" style={{ color: trtVar(g, 'ink') }}>— {g}</span>
        ))}
        {summary.dummy.includes('soil') && <DummyBadge />}
        <span className="ml-auto text-[11px] text-muted">{centre}</span>
      </div>
      <div className="px-3 pb-3 pt-1 md:px-4">
        {!groups.length && <EmptyState title={ko.sawtooth.noPots} compact />}
        {groups.length > 0 && q.isPending && <Skeleton className="h-44" />}
        {option && <ChartFrame option={option} height={mobile ? 190 : 210} ariaLabel="처리군 평균 토양수분 7일과 처리 밴드" />}
      </div>
    </Card>
  )
}

function centreLabel(s: SoilSeries | undefined): string {
  if (!s) return ''
  const c = Object.entries(s.band_pct).map(([g, [lo, hi]]) => [g, (lo + hi) / 2] as const)
  if (c.length === 0) return ''
  const same = c.every(([, v]) => Math.abs(v - c[0][1]) < 0.5)
  return same ? ko.soilBand.sub(7, `${fmtNum(c[0][1], 0)}%`) : `7d · 중심 ${c.map(([g, v]) => `${g[0]} ${fmtNum(v, 0)}%`).join(' · ')}`
}
