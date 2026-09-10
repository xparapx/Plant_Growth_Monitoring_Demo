import type { EChartsOption } from '@/charts/echarts'
import type { Droop } from '@/api/types'
import { fmtNum } from '@/lib/format'
import { trtColor } from '@/lib/treat'
import { baseTooltip } from './common'

/** Rows for the most recent day that has any (dawn, pm) pair. */
export function latestDroopRows(d: Droop): { day: string | null; rows: Droop['rows'] } {
  const rows = d.rows ?? []
  if (!rows.length) return { day: null, rows: [] }
  const day = rows.reduce((m, r) => (r.day > m ? r.day : m), rows[0].day)
  return { day, rows: rows.filter((r) => r.day === day) }
}

/** Bar per pot for the latest day: fill by treatment, ink border, value label outside. */
export function droopOption(rows: Droop['rows']): EChartsOption {
  return {
    grid: { left: 40, right: 12, top: 30, bottom: 26 },
    tooltip: baseTooltip({
      formatter: (ps: unknown) => {
        const p = (Array.isArray(ps) ? ps[0] : ps) as { name: string; dataIndex: number } | undefined
        const r = p ? rows[p.dataIndex] : undefined
        return r ? `${r.pot.toUpperCase()} · ${r.day}<br/>dawn ${fmtNum(r.dawn_px, 0)} px → pm ${fmtNum(r.pm_px, 0)} px<br/>droop <b>${fmtNum(r.droop_pct, 1)} %</b>` : ''
      },
    }),
    xAxis: { type: 'category', data: rows.map((r) => r.pot.toUpperCase()), axisLabel: { fontSize: 11, fontWeight: 700 } },
    yAxis: { type: 'value', name: '%', nameGap: 8, axisLabel: { fontSize: 10 } },
    series: [{
      type: 'bar', name: 'droop', barMaxWidth: 34,
      data: rows.map((r) => ({
        value: r.droop_pct,
        itemStyle: { color: trtColor(r.treat, 'fill'), borderColor: trtColor(r.treat, 'ink'), borderWidth: 1.5, borderRadius: [3, 3, 0, 0] },
      })),
      label: { show: true, position: 'top', fontSize: 10.5, formatter: (p: { value: number }) => fmtNum(p.value, 1) },
    }],
  }
}
