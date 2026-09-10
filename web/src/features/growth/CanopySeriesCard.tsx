import { useMemo } from 'react'
import { useAnalytics } from '@/api/queries'
import type { Summary } from '@/api/types'
import { ChartFrame } from '@/charts/ChartFrame'
import { canopySeriesOption } from '@/charts/options/canopySeries'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryState } from '@/components/ui/QueryState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { useIsMobile } from '@/hooks/useBreakpoint'
import { ko } from '@/i18n/ko'
import { G } from './strings'

/** Dawn canopy projected area per pot over the run. */
export function CanopySeriesCard({ summary }: { summary: Summary }) {
  const mobile = useIsMobile()
  const q = useAnalytics('canopy')
  const pots = q.data?.pots?.length ?? 0
  const option = useMemo(() => (q.data && pots > 0 ? canopySeriesOption(q.data, mobile) : null), [q.data, pots, mobile])
  return (
    <Card>
      <SectionHeader title={ko.series.title} dummy={summary.dummy.includes('growth')} sub={G.seriesSub} />
      <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<Skeleton className={mobile ? 'h-60' : 'h-[330px]'} />}>
        {(c) => (option
          ? <ChartFrame option={option} height={mobile ? 240 : 330} ariaLabel={`화분별 새벽 캐노피 면적 추이 — ${c.pots.map((p) => p.plant_id.toUpperCase()).join(', ')}`} />
          : <EmptyState title={ko.series.none} compact />)}
      </QueryState>
    </Card>
  )
}
