import { m } from 'motion/react'
import { ENV_KEYS, type Summary } from '@/api/types'
import { cardEnter } from '@/components/ui/Card'
import { KpiTile } from '@/components/ui/KpiTile'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { AlertBanner } from '@/components/ui/AlertBanner'
import { ko } from '@/i18n/ko'
import { ENV_VAR } from '@/lib/treat'

export function EnvKpiRow({ summary }: { summary: Summary }) {
  const gone = ENV_KEYS.filter((k) => summary.env[k].missing).map((k) => summary.env[k].label)
  return (
    <m.div variants={cardEnter} className="md:col-span-2 xl:col-span-12">
      <SectionHeader title={ko.env.title} dummy={summary.dummy.includes('env')} />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        {ENV_KEYS.map((k) => {
          const e = summary.env[k]
          return (
            <KpiTile
              key={k}
              label={e.label}
              value={e.value}
              unit={e.unit}
              digits={e.digits}
              delta={k === 'lux' ? null : e.delta_1d}
              sub={k === 'lux' ? ' ' : undefined}
              spark={e.spark}
              color={`var(${ENV_VAR[k]})`}
              missing={e.missing}
              group={k === 'lux'}
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
