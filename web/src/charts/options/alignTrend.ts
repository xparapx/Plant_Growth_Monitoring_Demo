import type { EChartsOption } from '@/charts/echarts'
import type { AlignmentTrend } from '@/api/types'
import { fmtNum } from '@/lib/format'
import { TREAT_NAME, trtColor } from '@/lib/treat'
import { baseTooltip, legendTop } from './common'

/** Weekly group mean soil moisture, one line+marker per treatment. */
export function alignTrendOption(t: AlignmentTrend): EChartsOption {
  const groups = Object.keys(t.groups ?? {})
  return {
    grid: { left: 44, right: 16, top: 34, bottom: 28 },
    legend: legendTop({ data: groups.map((g) => TREAT_NAME[g] ?? g) }),
    tooltip: baseTooltip({ valueFormatter: (v: number | null) => (v === null || v === undefined ? '—' : `${fmtNum(v, 1)} %`) }),
    xAxis: { type: 'category', data: t.weeks ?? [], axisLabel: { fontSize: 10 }, boundaryGap: true },
    yAxis: { type: 'value', name: 'μ (%)', scale: true, axisLabel: { fontSize: 10, formatter: (v: number) => fmtNum(v, 0) } },
    series: groups.map((g) => ({
      type: 'line', name: TREAT_NAME[g] ?? g, data: (t.groups[g] ?? []).map((v) => v ?? null), connectNulls: false,
      symbol: 'circle', symbolSize: 7, lineStyle: { width: 2.5, color: trtColor(g, 'fill') }, itemStyle: { color: trtColor(g, 'fill') },
    })),
  }
}
