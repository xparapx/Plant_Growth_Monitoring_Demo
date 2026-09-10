import { useMemo } from 'react'
import { useSoil } from '@/api/queries'
import type { Summary } from '@/api/types'
import { ChartFrame } from '@/charts/ChartFrame'
import { sawtoothGridOption, sawtoothSingleOption } from '@/charts/options/sawtooth'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { useIsMobile } from '@/hooks/useBreakpoint'
import { ko } from '@/i18n/ko'
import { TREAT_NAME, trtVar } from '@/lib/treat'

export function SawtoothCard({ summary }: { summary: Summary }) {
  const mobile = useIsMobile()
  const q = useSoil('auto')
  const groups = summary.groups
  const grid = useMemo(() => (q.data && !mobile ? sawtoothGridOption(q.data, groups) : null), [q.data, groups, mobile])
  const hasPots = Object.keys(groups).length > 0
  return (
    <Card className="md:col-span-2 xl:col-span-12">
      <SectionHeader title={ko.sawtooth.title} dummy={summary.dummy.includes('soil')} sub="밴드(음영) 안에서 dose·soak·verify 폐루프 — 진폭은 붙들고 주기는 흘려보냅니다." />
      {!hasPots && <EmptyState title={ko.sawtooth.noPots} compact />}
      {hasPots && q.isPending && <Skeleton className="h-64" />}
      {hasPots && q.data && !mobile && grid && (
        <ChartFrame option={grid.option} height={Math.max(220, 118 * grid.rows + 40)} ariaLabel="화분별 토양수분 톱니 7일" />
      )}
      {hasPots && q.data && mobile && (
        <div className="snap-x -mx-4 flex gap-3 overflow-x-auto px-4 pb-2">
          {Object.entries(groups).flatMap(([treat, pots]) => pots.map((p) => (
            <div key={p} className="w-[86vw] flex-none rounded-md border border-border-soft p-2">
              <div className="mb-1 flex items-center gap-2 text-[12px]">
                <b className="num">{p.toUpperCase()}</b>
                <span className="label !text-[9.5px]" style={{ color: trtVar(treat, 'ink') }}>{TREAT_NAME[treat]}</span>
              </div>
              <ChartFrame option={sawtoothSingleOption(q.data!, p, treat)} height={200} ariaLabel={`${p} 토양수분 7일`} />
            </div>
          )))}
        </div>
      )}
    </Card>
  )
}
