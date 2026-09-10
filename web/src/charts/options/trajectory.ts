import type { EChartsOption } from '@/charts/echarts'
import type { SoilSeries } from '@/api/types'
import { cssVar } from '@/app/theme'
import { fmtNum } from '@/lib/format'
import { trtColor } from '@/lib/treat'
import { baseTooltip, timeAxis } from './common'
import { groupMeans } from './soilBand'

/** Mockup 3b: band rectangles (stable narrow, fluct wide), dashed centre, one line per group, captions top/bottom. */
export function trajectoryOption(soil: SoilSeries, groups: Record<string, string[]>): EChartsOption {
  const means = groupMeans(soil, groups)
  const treats = Object.keys(groups)
  const muted = cssVar('--ink-muted')
  const font = cssVar('--font-sans')
  const centres = treats.map((t) => soil.band_pct[t]).filter(Boolean).map(([lo, hi]) => (lo + hi) / 2)
  const centre = centres.length ? centres.reduce((a, b) => a + b, 0) / centres.length : null
  const cap = (t: string) => {
    const b = soil.band_pct[t]
    return b ? `${t} ${fmtNum(b[1], 0)}/${fmtNum(b[0], 0)} % (폭 ${fmtNum(b[1] - b[0], 0)})` : t
  }
  const graphic = [
    treats.includes('fluct') ? { type: 'text', left: 10, top: 8, silent: true, style: { text: cap('fluct'), fill: muted, fontSize: 11, fontFamily: font } } : null,
    treats.includes('stable') ? { type: 'text', left: 10, bottom: 8, silent: true, style: { text: `${cap('stable')}${centre !== null ? ` · 중심 ${fmtNum(centre, 0)}% 동일` : ''}`, fill: muted, fontSize: 11, fontFamily: font } } : null,
  ].filter(Boolean)
  return {
    grid: { left: 36, right: 12, top: 30, bottom: 34 },
    tooltip: baseTooltip({ valueFormatter: (v: number | null) => (v === null || v === undefined ? '—' : `${fmtNum(v, 1)} %`) }),
    xAxis: timeAxis(),
    yAxis: { type: 'value', min: soil.yrange[0], max: soil.yrange[1], splitNumber: 4, axisLabel: { fontSize: 10 } },
    graphic,
    series: treats.map((t, i) => {
      const b = soil.band_pct[t]
      return {
        type: 'line', name: t, showSymbol: false, sampling: 'lttb', smooth: 0.35,
        lineStyle: { width: 2.5, color: trtColor(t, 'fill') }, itemStyle: { color: trtColor(t, 'fill') },
        data: means[t] ?? [],
        markArea: b ? { silent: true, itemStyle: { color: trtColor(t, 'fill'), opacity: t === 'stable' ? 0.12 : 0.08 }, data: [[{ yAxis: b[0] }, { yAxis: b[1] }]] } : undefined,
        markLine: i === 0 && centre !== null ? { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: 'rgba(242,242,242,.3)', width: 1 }, label: { show: false }, data: [{ yAxis: centre }] } : undefined,
      }
    }),
  }
}
