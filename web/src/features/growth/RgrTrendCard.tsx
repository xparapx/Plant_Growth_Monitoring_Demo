import { useMemo } from 'react'
import { useAnalytics } from '@/api/queries'
import type { Canopy, Summary } from '@/api/types'
import { ChartFrame } from '@/charts/ChartFrame'
import type { EChartsOption } from '@/charts/echarts'
import { baseTooltip, timeAxis } from '@/charts/options/common'
import { Card } from '@/components/ui/Card'
import { DummyBadge } from '@/components/ui/DummyBadge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { useIsMobile } from '@/hooks/useBreakpoint'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { trtColor } from '@/lib/treat'

const DAYS = 14

/** Mockup 3c: "RGR 추이 — 처리군 평균" — daily RGR of the group-mean canopy, (ln A₂ − ln A₁)/Δt, one line per group. */
export function RgrTrendCard({ summary }: { summary: Summary }) {
  const mobile = useIsMobile()
  const q = useAnalytics('canopy')
  const option = useMemo(() => (q.data && q.data.pots.length ? rgrTrendOption(q.data, summary.groups) : null), [q.data, summary.groups])
  return (
    <Card className="md:col-span-2 xl:col-span-8" padded={false}>
      <div className="flex items-baseline gap-3 px-5 pt-4">
        <span className="card-title">{ko.rgrTrend.title}</span>
        {summary.dummy.includes('growth') && <DummyBadge />}
        <span className="num ml-auto text-[11px] text-muted">{ko.rgrTrend.sub(DAYS)}</span>
      </div>
      <div className="px-3 pb-3 pt-1 md:px-4">
        {q.isPending && <Skeleton className="h-28" />}
        {q.data && !option && <EmptyState title={ko.series.none} compact />}
        {option && <ChartFrame option={option} height={mobile ? 150 : 130} ariaLabel="처리군 평균 상대생장률 추이" />}
      </div>
    </Card>
  )
}

/** Group-mean ln(area) per day, then the day-to-day slope in %/d. */
function rgrTrendOption(c: Canopy, groups: Record<string, string[]>): EChartsOption {
  const series = Object.entries(groups).map(([treat, ids]) => {
    const byDay = new Map<string, number[]>()
    for (const p of c.pots) {
      if (!ids.includes(p.plant_id)) continue
      p.ts.forEach((t, i) => {
        const a = p.area_cm2[i]
        if (a === null || a === undefined || a <= 0) return
        const day = t.slice(0, 10)
        byDay.set(day, [...(byDay.get(day) ?? []), Math.log(a)])
      })
    }
    const days = [...byDay.keys()].sort().slice(-DAYS - 1)
    const means = days.map((d) => { const v = byDay.get(d)!; return v.reduce((x, y) => x + y, 0) / v.length })
    const data: [string, number][] = []
    for (let i = 1; i < days.length; i++) {
      const dt = (Date.parse(days[i]) - Date.parse(days[i - 1])) / 86_400_000
      if (dt > 0) data.push([days[i], ((means[i] - means[i - 1]) / dt) * 100])
    }
    return {
      type: 'line', name: treat, data, showSymbol: false, smooth: 0.4,
      lineStyle: { width: 2.5, color: trtColor(treat, 'fill') }, itemStyle: { color: trtColor(treat, 'fill') },
      endLabel: { show: true, formatter: treat, color: trtColor(treat, 'ink'), fontSize: 10, offset: [4, 0] },
    }
  })
  return {
    grid: { left: 36, right: 44, top: 10, bottom: 24 },
    tooltip: baseTooltip({ valueFormatter: (v: number | null) => (v === null || v === undefined ? '—' : `${fmtNum(v, 2)} %/d`) }),
    xAxis: timeAxis(),
    yAxis: { type: 'value', scale: true, splitNumber: 3, axisLabel: { fontSize: 10, formatter: (v: number) => fmtNum(v, 1) } },
    series,
  }
}
