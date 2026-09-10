import ReactEChartsCore from 'echarts-for-react/lib/core'
import { useEffect, useMemo, useRef } from 'react'
import { useTheme } from '@/app/theme'
import { echarts, type EChartsOption } from './echarts'
import { ensureChartTheme } from './theme'

interface Props {
  option: EChartsOption
  height?: number
  ariaLabel: string
  summary?: string
  loading?: boolean
  className?: string
  onEvents?: Record<string, (p: unknown) => void>
}

/** Themed, responsive ECharts host.  Animates on the first render only; remounts on theme change. */
export function ChartFrame({ option, height = 280, ariaLabel, summary, loading, className = '', onEvents }: Props) {
  const { theme } = useTheme()
  const themeName = ensureChartTheme(theme)
  const firstRender = useRef(true)
  const opt = useMemo<EChartsOption>(() => ({ animation: firstRender.current, animationDuration: 600, animationEasing: 'cubicOut', aria: { enabled: true }, ...option }), [option])
  useEffect(() => { firstRender.current = false }, [])
  return (
    <div role="img" aria-label={ariaLabel} className={className}>
      <ReactEChartsCore
        key={themeName}
        echarts={echarts}
        option={opt}
        theme={themeName}
        notMerge
        lazyUpdate
        showLoading={loading}
        style={{ height, width: '100%' }}
        opts={{ renderer: 'canvas' }}
        onEvents={onEvents}
      />
      {summary && <p className="sr-only">{summary}</p>}
    </div>
  )
}
