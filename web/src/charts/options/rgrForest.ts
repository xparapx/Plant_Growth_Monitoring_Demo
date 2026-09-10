import type { EChartsOption } from '@/charts/echarts'
import type { Rgr } from '@/api/types'
import { cssVar } from '@/app/theme'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { TREAT_NAME, trtColor } from '@/lib/treat'
import { legendTop } from './common'

interface RenderApi { value: (i: number) => number | string; coord: (p: (number | string)[]) => [number, number] }

/** Horizontal CI bar with small end caps, drawn by a `custom` series. */
function ciRenderer(color: string) {
  return (_p: unknown, api: RenderApi) => {
    const [x0, y] = api.coord([api.value(0), api.value(2)])
    const [x1] = api.coord([api.value(1), api.value(2)])
    const cap = 5, style = { stroke: color, lineWidth: 2, fill: 'none' }
    return {
      type: 'group',
      children: [
        { type: 'line', shape: { x1: x0, y1: y, x2: x1, y2: y }, style },
        { type: 'line', shape: { x1: x0, y1: y - cap, x2: x0, y2: y + cap }, style },
        { type: 'line', shape: { x1: x1, y1: y - cap, x2: x1, y2: y + cap }, style },
      ],
    }
  }
}

/** Forest plot: pots on y (roster order), RGR on x, ±95 % CI bars, dotted group means. */
export function rgrForestOption(r: Rgr): EChartsOption {
  const pots = r.pots ?? []
  const cats = pots.map((p) => p.pot.toUpperCase())
  const groups = Object.keys(r.groups ?? {})
  const series: unknown[] = []
  groups.forEach((g) => {
    const mine = pots.filter((p) => p.treat === g)
    const name = TREAT_NAME[g] ?? g
    const mean = r.groups[g]?.mean
    series.push({
      type: 'custom', name, z: 1, silent: true, renderItem: ciRenderer(trtColor(g, 'fill')),
      encode: { x: [0, 1], y: 2 },
      data: mine.filter((p) => p.ci95).map((p) => [p.ci95![0], p.ci95![1], p.pot.toUpperCase()]),
    })
    series.push({
      type: 'scatter', name, z: 2, symbolSize: 12,
      itemStyle: { color: trtColor(g, 'fill'), borderColor: cssVar('--bg-elev'), borderWidth: 2 },
      data: mine.map((p) => [p.rgr, p.pot.toUpperCase()]),
      markLine: mean !== undefined && Number.isFinite(mean) ? {
        silent: true, symbol: 'none', animation: false,
        lineStyle: { type: 'dotted', width: 1.5, color: trtColor(g, 'fill') },
        label: { show: false }, data: [{ xAxis: mean }],
      } : undefined,
    })
  })
  return {
    grid: { left: 44, right: 20, top: 34, bottom: 40 },
    legend: legendTop({ data: groups.map((g) => TREAT_NAME[g] ?? g) }),
    tooltip: {
      trigger: 'item', confine: true,
      formatter: (p: { seriesType: string; value: (number | string)[] }) => {
        if (p.seriesType !== 'scatter') return ''
        const pot = pots.find((x) => x.pot.toUpperCase() === p.value[1])
        if (!pot) return ''
        const ci = pot.ci95 ? ` [${fmtNum(pot.ci95[0], 4)}, ${fmtNum(pot.ci95[1], 4)}]` : ''
        return `${pot.pot.toUpperCase()} · ${TREAT_NAME[pot.treat ?? ''] ?? '—'}<br/>RGR <b>${fmtNum(pot.rgr, 4)}</b> /d${ci}<br/>R² ${fmtNum(pot.r2, 3)} · n=${pot.n}`
      },
    },
    xAxis: { type: 'value', name: ko.rgr.xTitle, nameLocation: 'middle', nameGap: 24, scale: true, axisLabel: { fontSize: 10, formatter: (v: number) => fmtNum(v, 3) } },
    yAxis: { type: 'category', data: cats, inverse: true, axisLabel: { fontSize: 11, fontWeight: 600 }, axisTick: { show: false } },
    series,
  }
}
