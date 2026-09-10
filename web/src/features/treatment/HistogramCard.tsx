import { useMemo } from 'react'
import { useAnalytics } from '@/api/queries'
import type { Summary } from '@/api/types'
import { ChartFrame } from '@/charts/ChartFrame'
import { histOption } from '@/charts/options/hist'
import { Card } from '@/components/ui/Card'
import { DummyBadge } from '@/components/ui/DummyBadge'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryState } from '@/components/ui/QueryState'
import { Skeleton } from '@/components/ui/Skeleton'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { TREAT_NAME, trtVar } from '@/lib/treat'
import { T } from './strings'

/** Mockup 3b right column, bottom: "수분 분포 (14d)" — measured ρ(w) per group, compact. */
export function HistogramCard({ summary }: { summary: Summary }) {
  const q = useAnalytics('histogram')
  const groups = q.data ? Object.keys(q.data.groups ?? {}) : []
  const option = useMemo(() => (q.data && groups.length ? histOption(q.data, true) : null), [q.data, groups.length])
  return (
    <Card padded className="flex-1">
      <div className="mb-1 flex items-center gap-2">
        <span className="card-title !text-[12.5px]">{ko.hist.title}</span>
        {summary.dummy.includes('soil') && <DummyBadge />}
      </div>
      <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<Skeleton className="h-40" />}>
        {(h) => (
          <>
            {!option && <EmptyState title={T.histNone} compact />}
            {option && (
              <ChartFrame
                option={option} height={170}
                ariaLabel={`처리군별 토양수분 분포 — ${groups.map((g) => `${TREAT_NAME[g]} μ ${fmtNum(h.groups[g].mu, 1)}% σ ${fmtNum(h.groups[g].sd, 1)}`).join(', ')}`}
              />
            )}
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[10.5px] text-muted">
              {groups.map((g) => (
                <span key={g} className="num"><b style={{ color: trtVar(g, 'ink') }}>{g}</b> μ {fmtNum(h.groups[g].mu, 1)} σ {fmtNum(h.groups[g].sd, 1)} n={h.groups[g].n}</span>
              ))}
              {h.e_w !== null && <span className="num">E[w] {fmtNum(h.e_w, 1)} %</span>}
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-muted">{ko.hist.caption}</p>
          </>
        )}
      </QueryState>
    </Card>
  )
}
