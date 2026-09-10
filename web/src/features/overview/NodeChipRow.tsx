import { m } from 'motion/react'
import type { Summary } from '@/api/types'
import { cardEnter } from '@/components/ui/Card'
import { StatusChip } from '@/components/ui/StatusChip'
import { AlertBanner } from '@/components/ui/AlertBanner'
import { ko } from '@/i18n/ko'
import { fmtAgoMin } from '@/lib/format'
import { useLiveStore } from '@/live/liveStore'

/** Node freshness chips (ENV / P1..PN / CAM) — one strip under the gauge row. */
export function NodeChipRow({ summary }: { summary: Summary }) {
  const live = useLiveStore()
  const alerts = summary.alerts.filter((a) => a.code === 'stuck_sensor' || a.code === 'verify_fail')
  return (
    <m.div variants={cardEnter} className="flex flex-wrap items-center gap-2 md:col-span-2 xl:col-span-12">
      <span className="label mr-1">{ko.nodes.title}</span>
      {summary.nodes.map((n) => {
        const detail = !n.real ? ko.common.notConnected : n.stuck ? ko.nodes.stuck : fmtAgoMin(n.minutes_ago)
        const key = n.kind === 'env' ? 'env' : n.kind === 'cam' ? 'growth' : n.pot ?? ''
        const pulseKey = n.kind === 'pot' ? live.lastPotEventAt[key] : live.lastEventAt[key]
        return <StatusChip key={n.name} label={n.name} state={n.state} detail={detail} pulseKey={pulseKey} title={n.last_ts ?? undefined} />
      })}
      {alerts.length > 0 && (
        <div className="flex w-full flex-col gap-2">
          {alerts.map((a) => <AlertBanner key={a.code + (a.pots ?? []).join()} level="bad">{a.text}</AlertBanner>)}
        </div>
      )}
    </m.div>
  )
}
