import type { EChartsOption } from '@/charts/echarts'
import type { DroopTimeline } from '@/api/types'
import { fmtNum } from '@/lib/format'
import { trtColor } from '@/lib/treat'
import { baseTooltip, legendTop } from './common'

/** Daily droop % per pot over the last 14 d; colour = treatment ink. */
export function droopTimelineOption(t: DroopTimeline): EChartsOption {
  const pots = t.pots ?? []
  return {
    grid: { left: 40, right: 12, top: 30, bottom: 26 },
    legend: legendTop({ data: pots.map((p) => p.plant_id.toUpperCase()), itemGap: 10 }),
    tooltip: baseTooltip({ valueFormatter: (v: number | null) => (v === null || v === undefined ? '—' : `${fmtNum(v, 1)} %`) }),
    xAxis: { type: 'category', data: (t.days ?? []).map((d) => d.slice(5)), axisLabel: { fontSize: 10 }, boundaryGap: false },
    yAxis: { type: 'value', name: '%', nameGap: 8, axisLabel: { fontSize: 10 } },
    series: pots.map((p) => ({
      type: 'line', name: p.plant_id.toUpperCase(), data: (p.droop_pct ?? []).map((v) => v ?? null), connectNulls: false,
      symbol: 'circle', symbolSize: 4, lineStyle: { width: 2.2, color: trtColor(p.treat, 'ink') }, itemStyle: { color: trtColor(p.treat, 'ink') },
    })),
  }
}
