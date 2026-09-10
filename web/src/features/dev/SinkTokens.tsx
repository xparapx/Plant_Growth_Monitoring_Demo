import { useEffect, useMemo, useState } from 'react'
import { useTheme } from '@/app/theme'
import { ChartFrame } from '@/charts/ChartFrame'
import type { EChartsOption } from '@/charts/echarts'
import { Card } from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'

const TOKENS = ['--bg', '--bg-elev', '--ink', '--primary', '--accent', '--stable', '--stable-ink', '--fluct', '--fluct-ink', '--env-vpd', '--env-temp', '--env-hum', '--env-co2', '--env-lux']

export function SinkTokens() {
  const { theme } = useTheme()
  const [vals, setVals] = useState<Record<string, string>>({})
  useEffect(() => {
    const cs = getComputedStyle(document.documentElement)
    setVals(Object.fromEntries(TOKENS.map((t) => [t, cs.getPropertyValue(t).trim()])))
  }, [theme])
  const option = useMemo<EChartsOption>(() => sampleLine(), [])
  return (
    <section id="tokens" className="scroll-mt-20 flex flex-col gap-4">
      <Card animate={false}>
        <SectionHeader title="Colour tokens" sub={`getComputedStyle(:root) · theme=${theme}`} />
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
          {TOKENS.map((t) => (
            <li key={t} className="flex items-center gap-2 rounded-md border border-border-soft p-2">
              <span className="h-8 w-8 flex-none rounded-md border border-border-soft" style={{ background: `var(${t})` }} aria-hidden="true" />
              <span className="min-w-0">
                <span className="num block truncate text-[11px] font-semibold">{t}</span>
                <span className="num block text-[10.5px] text-muted">{vals[t] ?? '…'}</span>
              </span>
            </li>
          ))}
        </ul>
      </Card>
      <Card animate={false}>
        <SectionHeader title="ChartFrame — line sample" sub="ECharts, theme registered from CSS variables; remounts on theme change" />
        <ChartFrame option={option} height={240} ariaLabel="샘플 선 그래프" summary="두 처리군의 7일 샘플 추세" />
      </Card>
    </section>
  )
}

function sampleLine(): EChartsOption {
  const days = Array.from({ length: 7 }, (_, i) => `09-${String(3 + i).padStart(2, '0')}`)
  const a = [11.5, 13.2, 15.4, 17.6, 20.4, 23.5, 27.1], b = [11.3, 12.9, 14.6, 16.7, 19.0, 21.7, 24.9]
  return {
    grid: { left: 44, right: 14, top: 30, bottom: 28 },
    legend: { top: 0, left: 0, icon: 'roundRect', data: ['STABLE', 'FLUCTUATING'] },
    tooltip: { trigger: 'axis', confine: true },
    xAxis: { type: 'category', data: days },
    yAxis: { type: 'value', name: 'cm²', scale: true },
    series: [
      { type: 'line', name: 'STABLE', data: a, smooth: false, symbolSize: 5, lineStyle: { width: 3 } },
      { type: 'line', name: 'FLUCTUATING', data: b, smooth: false, symbolSize: 5, lineStyle: { width: 3, type: 'dashed' } },
    ],
  }
}
