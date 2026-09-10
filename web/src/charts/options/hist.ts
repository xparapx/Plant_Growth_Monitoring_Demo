import type { EChartsOption } from '@/charts/echarts'
import type { Histogram } from '@/api/types'
import { cssVar } from '@/app/theme'
import { fmtNum } from '@/lib/format'
import { TREAT_NAME, trtColor } from '@/lib/treat'
import { baseTooltip, legendTop } from './common'

const OPACITY: Record<string, number> = { stable: 0.7, fluct: 0.55 }

/** Legend label: `Stable  μ=41.2  σ=1.9` */
export function histLegendName(g: string, mu: number, sd: number): string {
  const raw = TREAT_NAME[g] ?? g.toUpperCase()
  const title = raw.charAt(0) + raw.slice(1).toLowerCase()
  return `${title}  μ=${fmtNum(mu, 1)}  σ=${fmtNum(sd, 1)}`
}

/** Overlaid probability histograms ρ(w) per treatment group, bars centred on bin midpoints (value x-axis). */
export function histOption(h: Histogram, mobile = false): EChartsOption {
  const edges = h.edges ?? []
  const centres = edges.length > 1 ? edges.slice(0, -1).map((e, i) => (e + edges[i + 1]) / 2) : []
  const groups = Object.keys(h.groups ?? {})
  const names = groups.map((g) => histLegendName(g, h.groups[g].mu, h.groups[g].sd))
  const series = groups.map((g, gi) => {
    const grp = h.groups[g]
    return {
      type: 'bar', name: names[gi], barGap: '-100%', barCategoryGap: '8%',
      data: centres.map((c, i) => [c, grp.prob[i] ?? 0]),
      itemStyle: { color: trtColor(g, 'fill'), opacity: OPACITY[g] ?? 0.6, borderColor: trtColor(g, 'ink'), borderWidth: 1 },
      emphasis: { itemStyle: { opacity: 0.9 } },
      markLine: gi === 0 && h.e_w !== null ? {
        silent: true, symbol: 'none', animation: false,
        lineStyle: { type: 'dotted', width: 1.5, color: cssVar('--ink') },
        label: { formatter: 'E[w]', position: 'end', color: cssVar('--ink'), fontSize: 11 },
        data: [{ xAxis: h.e_w }],
      } : undefined,
    }
  })
  return {
    grid: { left: 48, right: 24, top: mobile ? 44 : 34, bottom: 40 },
    legend: legendTop({ data: names }),
    tooltip: baseTooltip({
      formatter: (ps: unknown) => {
        const arr = (Array.isArray(ps) ? ps : [ps]) as { seriesName: string; value: [number, number]; marker: string }[]
        if (!arr.length) return ''
        const c = arr[0].value[0]
        const w = edges.length ? (edges[1] - edges[0]) / 2 : 0
        return `w ${fmtNum(c - w, 1)}–${fmtNum(c + w, 1)} %<br/>` + arr.map((p) => `${p.marker} ${p.seriesName.split('  ')[0]} <b>${fmtNum(p.value[1], 3)}</b>`).join('<br/>')
      },
    }),
    xAxis: {
      type: 'value', name: 'soil moisture w (%)', nameLocation: 'middle', nameGap: 24,
      min: edges[0] ?? 0, max: edges[edges.length - 1] ?? 100,
      axisLabel: { formatter: (v: number) => fmtNum(v, 1), fontSize: 10 }, splitLine: { show: false },
    },
    yAxis: { type: 'value', name: 'ρ(w)', nameGap: 8, axisLabel: { fontSize: 10, formatter: (v: number) => fmtNum(v, 2) } },
    series,
  }
}
