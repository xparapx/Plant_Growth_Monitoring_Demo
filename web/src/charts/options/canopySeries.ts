import type { EChartsOption } from '@/charts/echarts'
import type { Canopy } from '@/api/types'
import { fmtNum } from '@/lib/format'
import { trtColor } from '@/lib/treat'
import { baseTooltip, legendTop, timeAxis } from './common'

/** Dawn canopy area per pot over time; line+marker, colour = treatment ink. */
export function canopySeriesOption(c: Canopy, mobile = false): EChartsOption {
  const pots = c.pots ?? []
  return {
    grid: { left: 48, right: 16, top: mobile ? 44 : 36, bottom: 28 },
    legend: legendTop({ data: pots.map((p) => p.plant_id.toUpperCase()), itemGap: 10 }),
    tooltip: baseTooltip({ valueFormatter: (v: number | null) => (v === null || v === undefined ? '—' : `${fmtNum(v, 1)} cm²`) }),
    xAxis: timeAxis(),
    yAxis: { type: 'value', name: 'cm²', nameGap: 8, scale: true, axisLabel: { fontSize: 10 } },
    series: pots.map((p) => ({
      type: 'line', name: p.plant_id.toUpperCase(), connectNulls: false,
      data: (p.ts ?? []).map((t, i) => [t, p.area_cm2?.[i] ?? null]),
      symbol: 'circle', symbolSize: 6, lineStyle: { width: 3, color: trtColor(p.treat, 'ink') }, itemStyle: { color: trtColor(p.treat, 'ink') },
    })),
  }
}
