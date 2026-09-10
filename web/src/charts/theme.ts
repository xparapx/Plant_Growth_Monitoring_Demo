import { cssVar } from '@/app/theme'
import { echarts } from './echarts'

const registered = new Set<string>()

/** Registers `plant-light` / `plant-dark` from the live CSS variables; returns the theme name. */
export function ensureChartTheme(theme: 'light' | 'dark'): string {
  const name = `plant-${theme}`
  if (registered.has(name)) return name
  const ink = cssVar('--ink'), muted = cssVar('--ink-muted'), border = cssVar('--border-soft'), elev = cssVar('--bg-elev')
  const font = cssVar('--font-sans') || 'system-ui, sans-serif'
  const axis = {
    axisLine: { lineStyle: { color: border } },
    axisTick: { lineStyle: { color: border } },
    axisLabel: { color: muted, fontFamily: font, fontSize: 11 },
    splitLine: { lineStyle: { color: border, opacity: 0.6 } },
    nameTextStyle: { color: muted, fontSize: 11 },
  }
  echarts.registerTheme(name, {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: font, color: ink },
    color: [cssVar('--stable-ink'), cssVar('--fluct-ink'), cssVar('--primary'), cssVar('--accent')],
    categoryAxis: axis, valueAxis: axis, timeAxis: axis, logAxis: axis,
    legend: { textStyle: { color: ink, fontSize: 11 }, itemWidth: 14, itemHeight: 8 },
    tooltip: {
      backgroundColor: elev, borderColor: border, textStyle: { color: ink, fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,.12); border-radius: 8px;',
    },
    title: { textStyle: { color: ink, fontSize: 12, fontWeight: 700 } },
    line: { smooth: false, symbolSize: 5 },
  })
  registered.add(name)
  return name
}

export function resetChartThemes() { registered.clear() }
