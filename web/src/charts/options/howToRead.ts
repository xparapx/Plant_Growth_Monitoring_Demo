import type { EChartsOption } from '@/charts/echarts'
import type { Reference } from '@/api/types'
import { cssVar } from '@/app/theme'
import { trtColor } from '@/lib/treat'

const W_MIN = 15, W_MAX = 70
const clip0 = (x: number) => Math.max(0, x)

/** Synthetic reference curves — never fitted to data (manual rule). */
export const concave = (w: number) => 100 * (1 - Math.exp(-2.6 * clip0((w - 18) / 44)))
export const convex = (w: number) => 100 * Math.pow(clip0((w - 15) / 55), 2.2)

function sample(f: (w: number) => number): [number, number][] {
  const pts: [number, number][] = []
  for (let w = W_MIN; w <= W_MAX + 1e-9; w += 0.5) pts.push([w, f(w)])
  return pts
}

/** One reference panel: grey curve + dashed chord (p05→p95) + vertical gap at w = mean (Jensen's inequality). */
export function howToReadOption(kind: 'concave' | 'convex', ref: Reference | undefined, mobile = false): EChartsOption {
  const f = kind === 'concave' ? concave : convex
  const accent = trtColor(kind === 'concave' ? 'stable' : 'fluct', 'ink')
  const grey = cssVar('--ink-muted')
  const p05 = ref?.p05 ?? null, p95 = ref?.p95 ?? null, mean = ref?.mean ?? null
  const hasRef = p05 !== null && p95 !== null && p95 > p05
  const series: unknown[] = [
    { type: 'line', name: 'f(w)', data: sample(f), showSymbol: false, silent: true, lineStyle: { width: 2.5, color: grey }, itemStyle: { color: grey } },
  ]
  if (hasRef) {
    series.push({
      type: 'line', name: 'chord', data: [[p05, f(p05)], [p95, f(p95)]], showSymbol: true, symbolSize: 5, silent: true,
      lineStyle: { width: 1.5, type: 'dashed', color: grey }, itemStyle: { color: grey },
    })
    if (mean !== null && mean > p05 && mean < p95) {
      const chordAt = f(p05) + ((mean - p05) / (p95 - p05)) * (f(p95) - f(p05))
      series.push({
        type: 'line', name: 'gap', data: [[mean, chordAt], [mean, f(mean)]], showSymbol: true, symbolSize: 6, silent: true,
        lineStyle: { width: 3, color: accent }, itemStyle: { color: accent },
        label: { show: false },
      })
    }
  }
  return {
    grid: { left: 36, right: 14, top: 14, bottom: mobile ? 30 : 28 },
    tooltip: { show: false },
    xAxis: { type: 'value', min: W_MIN, max: W_MAX, name: 'w (%)', nameLocation: 'middle', nameGap: 18, splitLine: { show: false }, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', min: 0, max: 100, name: 'growth', nameGap: 8, axisLabel: { fontSize: 10 }, splitNumber: 2 },
    series,
  }
}
