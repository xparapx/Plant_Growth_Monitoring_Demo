import type { EChartsOption } from '@/charts/echarts'
import type { SoilSeries } from '@/api/types'
import { cssVar } from '@/app/theme'
import { TREAT_NAME, trtColor } from '@/lib/treat'
import { baseTooltip, timeAxis } from './common'

/** N rows x G columns of pot sawtooth traces in ONE ECharts instance (grouped by treatment). */
export function sawtoothGridOption(soil: SoilSeries, groups: Record<string, string[]>): { option: EChartsOption; rows: number } {
  const cols = Object.keys(groups)
  const rows = Math.max(1, ...cols.map((g) => groups[g].length))
  const byPot = new Map(soil.pots.map((p) => [p.plant_id, p]))
  const grids: unknown[] = [], xAxes: unknown[] = [], yAxes: unknown[] = [], series: unknown[] = [], titles: unknown[] = []
  const top = 30, bottom = 26, hGap = 5, vGap = 3
  const colW = (100 - 6 - hGap * (cols.length - 1)) / cols.length
  const rowH = (100 - (top + bottom) / 3 - vGap * (rows - 1)) / rows
  let idx = 0
  cols.forEach((treat, ci) => {
    const pots = groups[treat]
    const band = soil.band_pct[treat]
    titles.push({ text: TREAT_NAME[treat] ?? treat.toUpperCase(), left: `${6 + ci * (colW + hGap) + colW / 2}%`, top: 6, textAlign: 'center', textStyle: { fontSize: 11, color: trtColor(treat, 'ink') } })
    pots.forEach((pid, ri) => {
      const g = { left: `${6 + ci * (colW + hGap)}%`, width: `${colW}%`, top: `${top / 3 + ri * (rowH + vGap)}%`, height: `${rowH}%` }
      grids.push(g)
      xAxes.push({ ...timeAxis({ gridIndex: idx, axisLabel: { show: ri === rows - 1, hideOverlap: true, formatter: { day: '{MM}-{dd}', hour: '{HH}:{mm}' } } }) })
      yAxes.push({
        type: 'value', gridIndex: idx, min: soil.yrange[0], max: soil.yrange[1],
        name: pid.toUpperCase(), nameLocation: 'middle', nameGap: 26, nameTextStyle: { color: trtColor(treat, 'ink'), fontWeight: 700, fontSize: 10 },
        axisLabel: { show: ci === 0, fontSize: 10 }, splitLine: { show: true, lineStyle: { opacity: 0.35 } }, splitNumber: 3,
      })
      const p = byPot.get(pid)
      series.push({
        type: 'line', name: pid.toUpperCase(), xAxisIndex: idx, yAxisIndex: idx, showSymbol: false, sampling: 'lttb',
        lineStyle: { width: 2, color: trtColor(treat, 'fill') }, itemStyle: { color: trtColor(treat, 'fill') },
        data: p ? p.ts.map((t, i) => [t, p.pct[i]]) : [],
        markArea: band ? { silent: true, itemStyle: { color: trtColor(treat, 'fill'), opacity: 0.10 }, data: [[{ yAxis: band[0] }, { yAxis: band[1] }]] } : undefined,
      })
      idx++
    })
  })
  return {
    rows,
    option: {
      title: titles, grid: grids, xAxis: xAxes, yAxis: yAxes, series,
      tooltip: baseTooltip({ valueFormatter: (v: number) => `${Number(v).toFixed(1)} %` }),
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
    },
  }
}

/** One pot, one chart (mobile swiper). */
export function sawtoothSingleOption(soil: SoilSeries, pid: string, treat: string | null): EChartsOption {
  const p = soil.pots.find((x) => x.plant_id === pid)
  const band = treat ? soil.band_pct[treat] : undefined
  return {
    grid: { left: 40, right: 12, top: 14, bottom: 26 },
    xAxis: timeAxis(),
    yAxis: { type: 'value', min: soil.yrange[0], max: soil.yrange[1], splitNumber: 4, axisLabel: { fontSize: 10 } },
    tooltip: baseTooltip({ valueFormatter: (v: number) => `${Number(v).toFixed(1)} %` }),
    series: [{
      type: 'line', name: pid.toUpperCase(), showSymbol: false, sampling: 'lttb',
      lineStyle: { width: 2, color: trtColor(treat, 'fill') }, itemStyle: { color: trtColor(treat, 'fill') },
      areaStyle: { color: trtColor(treat, 'fill'), opacity: 0.08 },
      data: p ? p.ts.map((t, i) => [t, p.pct[i]]) : [],
      markArea: band ? { silent: true, itemStyle: { color: trtColor(treat, 'fill'), opacity: 0.10 }, data: [[{ yAxis: band[0] }, { yAxis: band[1] }]] } : undefined,
    }],
    backgroundColor: 'transparent',
    textStyle: { color: cssVar('--ink') },
  }
}
