import type { Schedule } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { Countdown } from '@/components/ui/Countdown'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { ko } from '@/i18n/ko'
import { fmtDateTime } from '@/lib/format'
import { phaseLabel } from './jobUtils'
import { cs } from './strings'

export function NextRunCard({ schedule }: { schedule: Schedule }) {
  const t = schedule.timer
  return (
    <Card className="xl:col-span-7">
      <SectionHeader title={ko.capture.next} sub={cs.tz(schedule.tz)} />
      <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
        <Countdown to={schedule.next.at} format="hms" className="text-[40px] font-semibold leading-none md:text-[48px]" />
        <span className="mb-1 inline-flex items-center gap-2">
          <span className="rounded-full bg-stable px-2.5 py-0.5 text-[10.5px] font-medium tracking-[.06em] text-stable-on">{phaseLabel(schedule.next.phase).toUpperCase()}</span>
          <span className="num text-[12px] text-muted">{fmtDateTime(schedule.next.at)}</span>
        </span>
      </div>
      <div className="mt-3 flex flex-col gap-1 text-[12.5px] text-muted">
        <div className="num">{ko.capture.schedule(schedule.dawn, schedule.pm)}</div>
        <div className="num">{cs.expected(schedule.expected_shot.dawn, schedule.expected_shot.pm)}</div>
        {t !== null && <div className="num">{cs.timer(t.active, t.next ? fmtDateTime(t.next) : null)}</div>}
      </div>
    </Card>
  )
}
