import { useMemo } from 'react'
import { useAnalytics } from '@/api/queries'
import type { Summary } from '@/api/types'
import { ChartFrame } from '@/charts/ChartFrame'
import { alignTrendOption } from '@/charts/options/alignTrend'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryState } from '@/components/ui/QueryState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { useIsMobile } from '@/hooks/useBreakpoint'
import { ko } from '@/i18n/ko'
import { T } from './strings'

/** Weekly group means — do the two centres stay aligned over the run? */
export function AlignTrendCard({ summary }: { summary: Summary }) {
  const mobile = useIsMobile()
  const q = useAnalytics('alignment-trend')
  const hasData = !!q.data && (q.data.weeks?.length ?? 0) > 0 && Object.keys(q.data.groups ?? {}).length > 0
  const option = useMemo(() => (q.data && hasData ? alignTrendOption(q.data) : null), [q.data, hasData])
  return (
    <Card>
      <SectionHeader title={ko.align.title} dummy={summary.dummy.includes('soil')} sub={T.alignSub} />
      <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<Skeleton className="h-56" />}>
        {() => (option
          ? <ChartFrame option={option} height={mobile ? 220 : 260} ariaLabel="주별 처리군 평균 토양수분 추이" />
          : <EmptyState title={T.alignNone} compact />)}
      </QueryState>
    </Card>
  )
}
