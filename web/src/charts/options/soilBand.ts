import type { EChartsOption } from '@/charts/echarts'
import type { SoilSeries } from '@/api/types'
import { cssVar } from '@/app/theme'
import { fmtNum } from '@/lib/format'
import { trtColor } from '@/lib/treat'
import { baseTooltip, timeAxis } from './common'

/** Mean soil moisture per treatment over time (pots averaged on shared bucket timestamps). */
export function groupMeans(soil: SoilSeries, groups: Record<string, string[]>): Record<string, [string, number | null][]> {
  const out: Record<string, [string, number | null][]> = {}
  for (const [treat, pots] of Object.entries(groups)) {
    const acc = new Map<string, { s: number; n: number }>()
    for (const p of soil.pots) {
      if (!pots.includes(p.plant_id)) continue
      p.ts.forEach((t, i) => {
        const v = p.pct[i]
        if (v === null || v === undefined || !Number.isFinite(v)) return
        const a = acc.get(t) ?? { s: 0, n: 0 }
        a.s += v; a.n += 1
        acc.set(t, a)
      })
    }
    out[treat] = [...acc.entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([t, a]) => [t, a.n ? a.s / a.n : null])
  }
  return out
}

/** Mockup 3a chart: one line per group, band as a soft markArea, dashed centre line, band captions top/bottom. */
export function groupMeanOption(soil: SoilSeries, groups: Record<string, string[]>, days = 7): EChartsOption {
  const means = groupMeans(soil, groups)
  const treats = Object.keys(groups)
  const centres = treats.map((t) => soil.band_pct[t]).filter(Boolean).map(([lo, hi]) => (lo + hi) / 2)
  const centre = centres.length ? centres.reduce((a, b) => a + b, 0) / centres.length : null
  const muted = cssVar('--ink-muted')
  const graphic = treats.map((t, i) => {
    const b = soil.band_pct[t]
    if (!b) return null
    return {
      type: 'text', left: 8, [t === 'fluct' || i === 0 ? 'top' : 'bottom']: t === 'fluct' || i === 0 ? 6 : 6,
      style: { text: `${t} band ${fmtNum(b[1], 0)} / ${fmtNum(b[0], 0)} %`, fill: muted, fontSize: 10, fontFamily: cssVar('--font-sans') },
      silent: true,
    }
  }).filter(Boolean)
  return {
    grid: { left: 36, right: 10, top: 22, bottom: 26 },
    tooltip: baseTooltip({ valueFormatter: (v: number | null) => (v === null || v === undefined ? '—' : `${fmtNum(v, 1)} %`) }),
    xAxis: timeAxis({ min: soil.pots[0]?.ts?.length ? undefined : Date.now() - days * 86_400_000 }),
    yAxis: { type: 'value', min: soil.yrange[0], max: soil.yrange[1], splitNumber: 3, axisLabel: { fontSize: 10, formatter: (v: number) => `${v}` } },
    graphic,
    series: treats.map((t, i) => {
      const b = soil.band_pct[t]
      return {
        type: 'line', name: t, showSymbol: false, sampling: 'lttb', smooth: 0.3,
        lineStyle: { width: 2, color: trtColor(t, 'fill') }, itemStyle: { color: trtColor(t, 'fill') },
        data: means[t] ?? [],
        markArea: b ? { silent: true, itemStyle: { color: trtColor(t, 'fill'), opacity: t === 'stable' ? 0.12 : 0.08 }, data: [[{ yAxis: b[0] }, { yAxis: b[1] }]] } : undefined,
        markLine: i === 0 && centre !== null ? { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: 'rgba(242,242,242,.3)', width: 1 }, label: { show: false }, data: [{ yAxis: centre }] } : undefined,
      }
    }),
  }
}
