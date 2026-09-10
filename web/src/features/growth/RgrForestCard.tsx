import type { UseQueryResult } from '@tanstack/react-query'
import { useMemo } from 'react'
import type { Rgr, Summary } from '@/api/types'
import { ChartFrame } from '@/charts/ChartFrame'
import { rgrForestOption } from '@/charts/options/rgrForest'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryState } from '@/components/ui/QueryState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { G } from './strings'

/** Forest plot of per-pot RGR ± 95 % CI with dotted group means. */
export function RgrForestCard({ summary, q }: { summary: Summary; q: UseQueryResult<Rgr> }) {
  const n = q.data?.pots?.length ?? 0
  const option = useMemo(() => (q.data && n > 0 ? rgrForestOption(q.data) : null), [q.data, n])
  return (
    <Card>
      <SectionHeader title={ko.rgr.title} dummy={summary.dummy.includes('growth')} sub={G.forestSub} />
      <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<Skeleton className="h-56" />}>
        {(r) => (
          <>
            {!option && <EmptyState title={G.forestNone} compact />}
            {option && (
              <ChartFrame
                option={option} height={60 + 34 * n + 40}
                ariaLabel={`화분별 상대생장률 forest plot — ${r.pots.map((p) => `${p.pot.toUpperCase()} ${fmtNum(p.rgr, 4)}/d`).join(', ')}`}
              />
            )}
            {r.worst_r2 !== null && <p className="mt-2 text-[12px] text-muted">{ko.rgr.caption(r.worst_r2)}</p>}
          </>
        )}
      </QueryState>
    </Card>
  )
}
