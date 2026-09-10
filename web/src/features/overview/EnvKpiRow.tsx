import { m } from 'motion/react'
import type { Summary } from '@/api/types'
import { cardEnter } from '@/components/ui/Card'
import { GaugeTile } from '@/components/ui/GaugeTile'
import { AlertBanner } from '@/components/ui/AlertBanner'
import { DummyBadge } from '@/components/ui/DummyBadge'
import { ko } from '@/i18n/ko'
import { ENV_GAUGE, ENV_ORDER } from '@/lib/env'
import { ENV_VAR } from '@/lib/treat'

/** Five needle gauges (mockup 3a, top row). Lux is shown in klx so the big number stays short. */
export function EnvKpiRow({ summary }: { summary: Summary }) {
  const gone = ENV_ORDER.filter((k) => summary.env[k].missing).map((k) => summary.env[k].label)
  const dummy = summary.dummy.includes('env')
  return (
    <m.div variants={cardEnter} className="md:col-span-2 xl:col-span-12">
      {dummy && <div className="mb-2"><DummyBadge /></div>}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5 xl:gap-3.5">
        {ENV_ORDER.map((k) => {
          const e = summary.env[k]
          const g = ENV_GAUGE[k]
          const klx = k === 'lux'
          const scale = klx ? 1 / 1000 : 1
          const v = e.value === null ? null : e.value * scale
          return (
            <GaugeTile
              key={k}
              label={g.label}
              value={v}
              unit={klx ? 'klx' : e.unit}
              digits={klx ? 1 : e.digits}
              range={[g.range[0] * scale, g.range[1] * scale]}
              optimal={[g.optimal[0] * scale, g.optimal[1] * scale]}
              rangeLabel={g.rangeLabel}
              color={`var(${ENV_VAR[k]})`}
              missing={e.missing}
              delta={klx ? undefined : e.delta_1d}
            />
          )
        })}
      </div>
      {summary.real_env && gone.length > 0 && (
        <div className="mt-3"><AlertBanner level="bad">{ko.env.missing(gone)}</AlertBanner></div>
      )}
    </m.div>
  )
}
