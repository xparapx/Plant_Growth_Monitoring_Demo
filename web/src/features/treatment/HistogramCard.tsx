import { useMemo } from 'react'
import { useAnalytics } from '@/api/queries'
import type { Summary } from '@/api/types'
import { ChartFrame } from '@/charts/ChartFrame'
import { histOption } from '@/charts/options/hist'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryState } from '@/components/ui/QueryState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { useIsMobile } from '@/hooks/useBreakpoint'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { TREAT_NAME, trtVar } from '@/lib/treat'
import { T } from './strings'

/** Measured soil-moisture distribution ρ(w) per group — the treatment check (same centre, different width). */
export function HistogramCard({ summary }: { summary: Summary }) {
  const mobile = useIsMobile()
  const q = useAnalytics('histogram')
  const groups = q.data ? Object.keys(q.data.groups ?? {}) : []
  const option = useMemo(() => (q.data && groups.length ? histOption(q.data, mobile) : null), [q.data, groups.length, mobile])
  return (
    <Card className="md:col-span-2">
      <SectionHeader title={ko.hist.title} dummy={summary.dummy.includes('soil')} sub={T.histSub} />
      <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<Skeleton className={mobile ? 'h-60' : 'h-[300px]'} />}>
        {(h) => (
          <>
            {!option && <EmptyState title={T.histNone} compact />}
            {option && (
              <ChartFrame
                option={option} height={mobile ? 240 : 300}
                ariaLabel={`처리군별 토양수분 분포 — ${groups.map((g) => `${TREAT_NAME[g]} μ ${fmtNum(h.groups[g].mu, 1)}% σ ${fmtNum(h.groups[g].sd, 1)}`).join(', ')}`}
              />
            )}
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted">
              {groups.map((g) => (
                <span key={g} className="num"><b style={{ color: trtVar(g, 'ink') }}>{TREAT_NAME[g]}</b> n={h.groups[g].n}</span>
              ))}
              {h.e_w !== null && <span className="num">E[w] = {fmtNum(h.e_w, 1)} %</span>}
            </div>
            <p className="mt-2 text-[12px] text-muted">{ko.hist.caption}</p>
          </>
        )}
      </QueryState>
    </Card>
  )
}
