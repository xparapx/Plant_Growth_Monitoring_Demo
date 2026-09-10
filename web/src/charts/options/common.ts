import type { EChartsOption } from '@/charts/echarts'
import { cssVar } from '@/app/theme'

export const GRID = { left: 44, right: 14, top: 28, bottom: 28, containLabel: false }

export function baseTooltip(extra: Record<string, unknown> = {}): Record<string, unknown> {
  return { trigger: 'axis', confine: true, axisPointer: { type: 'line', lineStyle: { color: cssVar('--ink-faint') } }, ...extra }
}

export function timeAxis(extra: Record<string, unknown> = {}): Record<string, unknown> {
  return { type: 'time', axisLabel: { hideOverlap: true, formatter: { day: '{MM}-{dd}', hour: '{HH}:{mm}' } }, splitLine: { show: false }, ...extra }
}

export function valueAxis(name?: string, extra: Record<string, unknown> = {}): Record<string, unknown> {
  return { type: 'value', name, nameLocation: 'end', nameGap: 8, scale: true, ...extra }
}

export const emptyOption = (text = '데이터 없음'): EChartsOption => ({
  title: { text, left: 'center', top: 'middle', textStyle: { color: cssVar('--ink-faint'), fontSize: 12, fontWeight: 500 } },
})

export const legendTop = (extra: Record<string, unknown> = {}) => ({ top: 0, left: 0, icon: 'roundRect', itemGap: 14, ...extra })
