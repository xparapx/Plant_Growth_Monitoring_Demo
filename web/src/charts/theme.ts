import { cssVar } from '@/app/theme'
import { echarts } from './echarts'

const registered = new Set<string>()

/** Registers `plant-light` / `plant-dark` from the live CSS variables; returns the theme name. */
export function ensureChartTheme(theme: 'light' | 'dark'): string {
  const name = `plant-${theme}`
  if (registered.has(name)) return name
  const ink = cssVar('--ink'), muted = cssVar('--ink-muted'), border = cssVar('--border-soft'), elev = cssVar('--bg-elev')
  const font = cssVar('--font-sans') || 'system-ui, sans-serif'
  const gridLine = theme === 'dark' ? 'rgba(242,242,242,.12)' : border
  const axis = {
    axisLine: { lineStyle: { color: gridLine } },
    axisTick: { lineStyle: { color: gridLine } },
    axisLabel: { color: muted, fontFamily: font, fontSize: 10.5 },
    splitLine: { lineStyle: { color: gridLine, opacity: 0.7, type: 'dashed' } },
    nameTextStyle: { color: muted, fontSize: 10.5 },
  }
  echarts.registerTheme(name, {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: font, color: ink },
    color: [cssVar('--stable-ink'), cssVar('--fluct-ink'), cssVar('--primary'), cssVar('--accent')],
    categoryAxis: axis, valueAxis: axis, timeAxis: axis, logAxis: axis,
    legend: { textStyle: { color: muted, fontSize: 11 }, itemWidth: 14, itemHeight: 3 },
    tooltip: {
      backgroundColor: theme === 'dark' ? cssVar('--bg-sunken') : elev, borderColor: theme === 'dark' ? 'rgba(242,242,242,.14)' : border,
      textStyle: { color: ink, fontSize: 12 },
      extraCssText: 'box-shadow: 0 8px 24px rgba(0,0,0,.28); border-radius: 10px;',
    },
    title: { textStyle: { color: ink, fontSize: 12, fontWeight: 600 } },
    line: { smooth: false, symbolSize: 5 },
  })
  registered.add(name)
  return name
}

export function resetChartThemes() { registered.clear() }
