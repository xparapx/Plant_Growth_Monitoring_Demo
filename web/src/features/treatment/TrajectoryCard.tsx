import { useMemo } from 'react'
import { useSoil } from '@/api/queries'
import type { Summary } from '@/api/types'
import { ChartFrame } from '@/charts/ChartFrame'
import { trajectoryOption } from '@/charts/options/trajectory'
import { Card } from '@/components/ui/Card'
import { DummyBadge } from '@/components/ui/DummyBadge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { useIsMobile } from '@/hooks/useBreakpoint'
import { ko } from '@/i18n/ko'

const DAYS = 14

/** Mockup 3b main chart: "수분 궤적 — 같은 중심, 다른 폭" — group means over 14 d with both bands drawn. */
export function TrajectoryCard({ summary }: { summary: Summary }) {
  const mobile = useIsMobile()
  const from = useMemo(() => new Date(Date.now() - DAYS * 86_400_000).toISOString(), [])
  const q = useSoil('auto', undefined, from)
  const groups = Object.keys(summary.groups)
  const option = useMemo(() => (q.data && groups.length ? trajectoryOption(q.data, summary.groups) : null), [q.data, summary.groups, groups.length])
  return (
    <Card className="md:col-span-2 xl:col-span-8" padded={false}>
      <div className="flex items-baseline gap-3 px-5 pt-4">
        <span className="card-title">{ko.trajectory.title}</span>
        {summary.dummy.includes('soil') && <DummyBadge />}
        <span className="ml-auto text-[11px] text-muted">{ko.trajectory.days(DAYS)}</span>
      </div>
      <div className="px-3 pb-3 pt-1 md:px-4">
        {!groups.length && <EmptyState title={ko.sawtooth.noPots} compact />}
        {groups.length > 0 && q.isPending && <Skeleton className="h-56" />}
        {option && <ChartFrame option={option} height={mobile ? 220 : 260} ariaLabel="처리군 평균 토양수분 14일 궤적과 밴드" />}
      </div>
    </Card>
  )
}
