import { useMemo } from 'react'
import { useAnalytics } from '@/api/queries'
import type { Summary } from '@/api/types'
import { ChartFrame } from '@/charts/ChartFrame'
import { droopOption, latestDroopRows } from '@/charts/options/droop'
import { droopTimelineOption } from '@/charts/options/droopTimeline'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryState } from '@/components/ui/QueryState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { useIsMobile } from '@/hooks/useBreakpoint'
import { ko } from '@/i18n/ko'
import { fmtNum, upper } from '@/lib/format'
import { T } from './strings'

/** Midday droop (dawn − pm)/dawn per pot for the latest paired day, plus a 14 d timeline. */
export function DroopCard({ summary }: { summary: Summary }) {
  const mobile = useIsMobile()
  const q = useAnalytics('droop')
  const tl = useAnalytics('droop-timeline')
  const latest = useMemo(() => (q.data ? latestDroopRows(q.data) : { day: null, rows: [] }), [q.data])
  const barOpt = useMemo(() => (latest.rows.length ? droopOption(latest.rows) : null), [latest])
  const tlOpt = useMemo(() => (tl.data && tl.data.pots?.length && tl.data.days?.length ? droopTimelineOption(tl.data) : null), [tl.data])
  return (
    <Card className="xl:col-span-6">
      <SectionHeader title={ko.droop.title} dummy={summary.dummy.includes('growth')} sub={latest.day ? T.droopDay(latest.day) : T.droopSub} />
      <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<Skeleton className="h-56" />}>
        {(d) => (
          <>
            {!d.has_both_phases && <EmptyState title={ko.droop.needBoth} compact />}
            {d.has_both_phases && !barOpt && <EmptyState title={ko.droop.none} compact />}
            {d.has_both_phases && barOpt && (
              <ChartFrame
                option={barOpt} height={mobile ? 200 : 230}
                ariaLabel={`화분별 정오 처짐 ${latest.day ?? ''} — ${latest.rows.map((r) => `${upper(r.pot)} ${fmtNum(r.droop_pct, 1)}%`).join(', ')}`}
              />
            )}
            {d.missing?.length > 0 && <p className="mt-1 text-[11px] text-warn-ink">{ko.droop.missing(d.missing.map(upper))}</p>}
          </>
        )}
      </QueryState>
      <div className="mt-4 border-t border-border-soft pt-3">
        <div className="label mb-1 !text-[10px]">{ko.droop.timeline}</div>
        {tl.isPending && <Skeleton className="h-36" />}
        {tl.error != null && !tl.data && <p className="text-[12px] text-bad-ink">{ko.common.error}</p>}
        {tl.data && !tlOpt && <EmptyState title={ko.droop.none} compact />}
        {tlOpt && <ChartFrame option={tlOpt} height={mobile ? 160 : 180} ariaLabel="화분별 정오 처짐 14일 추이" />}
      </div>
    </Card>
  )
}
