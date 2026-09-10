import { useMemo } from 'react'
import { useAnalytics } from '@/api/queries'
import type { Summary, Water } from '@/api/types'
import { ChartFrame } from '@/charts/ChartFrame'
import type { EChartsOption } from '@/charts/echarts'
import { baseTooltip, legendTop } from '@/charts/options/common'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { TREAT_NAME, trtColor, trtVar } from '@/lib/treat'

/** 관수 기록 (manual §17 item 3): cumulative water per group + dosing interval — an outcome, not a control. */
export function WaterCard({ summary }: { summary: Summary }) {
  const q = useAnalytics('water')
  const option = useMemo(() => (q.data ? dailyOption(q.data) : null), [q.data])
  return (
    <Card className="xl:col-span-6">
      <SectionHeader title={ko.water.title} dummy={summary.dummy.includes('pump')} sub="총 급수량은 통제하지 않습니다 — 결과로 따라 나오는 값입니다." />
      {q.isPending && <Skeleton className="h-48" />}
      {q.data && Object.keys(q.data.groups).length === 0 && <EmptyState title="급수 기록이 아직 없습니다" compact />}
      {q.data && Object.keys(q.data.groups).length > 0 && option && (
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
          <ChartFrame option={option} height={200} ariaLabel="처리군별 일일 급수량" />
          <dl className="flex flex-col gap-2">
            {Object.entries(q.data.groups).map(([g, v]) => (
              <div key={g} className="card-sub px-3 py-2">
                <dt className="label !text-[9.5px]" style={{ color: trtVar(g, 'ink') }}>{TREAT_NAME[g]}</dt>
                <dd className="num text-[18px] font-semibold">{fmtNum(v.total_ml / 1000, 2)} <span className="text-[11px] font-normal text-muted">L · {v.events}회</span></dd>
                <dd className="num text-[11px] text-muted">{ko.water.perPot} {fmtNum(v.ml_per_pot, 0)} mL</dd>
              </div>
            ))}
            <div className="text-[11px] text-muted">
              {ko.water.interval}: {q.data.pots.filter((p) => p.mean_interval_d !== null).map((p) => `${p.plant_id.toUpperCase()} ${fmtNum(p.mean_interval_d, 1)}${ko.water.days}`).join(' · ') || '—'}
            </div>
          </dl>
        </div>
      )}
    </Card>
  )
}

function dailyOption(w: Water): EChartsOption {
  const groups = Object.keys(w.daily.groups)
  return {
    grid: { left: 44, right: 10, top: 28, bottom: 26 },
    legend: legendTop({ data: groups.map((g) => TREAT_NAME[g] ?? g) }),
    tooltip: baseTooltip({ valueFormatter: (v: number) => `${fmtNum(v, 0)} mL` }),
    xAxis: { type: 'category', data: w.daily.days.map((d) => d.slice(5)), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: 'mL', axisLabel: { fontSize: 10 } },
    series: groups.map((g) => ({
      type: 'bar', name: TREAT_NAME[g] ?? g, data: w.daily.groups[g], barMaxWidth: 18,
      itemStyle: { color: trtColor(g, 'fill'), borderRadius: [3, 3, 0, 0] },
    })),
  }
}
