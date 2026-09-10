import { m } from 'motion/react'
import type { Summary } from '@/api/types'
import { cardEnter } from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { StatusChip } from '@/components/ui/StatusChip'
import { AlertBanner } from '@/components/ui/AlertBanner'
import { ko } from '@/i18n/ko'
import { fmtAgoMin } from '@/lib/format'
import { useLiveStore } from '@/live/liveStore'

export function NodeChipRow({ summary }: { summary: Summary }) {
  const live = useLiveStore()
  const alerts = summary.alerts.filter((a) => a.code === 'stuck_sensor' || a.code === 'verify_fail')
  return (
    <m.div variants={cardEnter} className="md:col-span-2 xl:col-span-12">
      <SectionHeader title={ko.nodes.title} />
      <div className="flex flex-wrap gap-2">
        {summary.nodes.map((n) => {
          const detail = !n.real ? ko.common.notConnected : n.stuck ? ko.nodes.stuck : fmtAgoMin(n.minutes_ago)
          const key = n.kind === 'env' ? 'env' : n.kind === 'cam' ? 'growth' : n.pot ?? ''
          const pulseKey = n.kind === 'pot' ? live.lastPotEventAt[key] : live.lastEventAt[key]
          return <StatusChip key={n.name} label={n.name} state={n.state} detail={detail} pulseKey={pulseKey} title={n.last_ts ?? undefined} />
        })}
      </div>
      {alerts.length > 0 && (
        <div className="mt-3 flex flex-col gap-2">
          {alerts.map((a) => <AlertBanner key={a.code + (a.pots ?? []).join()} level="bad">{a.text}</AlertBanner>)}
        </div>
      )}
    </m.div>
  )
}
