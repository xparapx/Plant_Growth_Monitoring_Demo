import { Link } from 'react-router-dom'
import { useCaptureJobs } from '@/api/queries'
import type { Job } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { StatusChip } from '@/components/ui/StatusChip'
import { phaseLabel, stateChip, stateLabel } from '@/features/capture/jobUtils'
import { ko } from '@/i18n/ko'
import { fmtDateTime } from '@/lib/format'

/** "촬영 일지" — the 3a filler proposed in the plan: the last few capture jobs with LED, drift and ok/n. */
export function CaptureLogCard() {
  const q = useCaptureJobs(6)
  return (
    <Card className="md:col-span-2 xl:col-span-12">
      <SectionHeader title={ko.captureLog.title} sub={ko.captureLog.sub} actions={<Link to="/camera" className="text-[11.5px] font-medium">{ko.capture.history} →</Link>} />
      {q.isPending && <Skeleton lines={3} />}
      {q.data && q.data.jobs.length === 0 && <EmptyState title={ko.captureLog.none} compact />}
      {q.data && q.data.jobs.length > 0 && (
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {q.data.jobs.map((j) => <Row key={j.id} j={j} />)}
        </ul>
      )}
    </Card>
  )
}

function Row({ j }: { j: Job }) {
  const ledOn = j.led?.installed ? j.steps.find((s) => s.name === 'led_on') : null
  const drift = j.drift?.level
  return (
    <li className="card-sub flex flex-col gap-1 px-3.5 py-2.5 text-[11.5px] text-muted">
      <div className="flex items-center gap-2">
        <span className="num text-[12.5px] font-medium text-ink">{fmtDateTime(j.started_at)}</span>
        <span className="rounded-full bg-elev px-2 py-0.5 text-[10px] font-medium uppercase tracking-[.08em] text-muted">{phaseLabel(j.phase)}</span>
        <span className="ml-auto"><StatusChip label={stateLabel(j.state)} state={stateChip(j.state)} /></span>
      </div>
      <div className="num flex flex-wrap gap-x-3 gap-y-0.5">
        <span>ok {j.ok_rows}/{j.n_rows}</span>
        <span>{ko.captureLog.led} {ledOn ? fmtDateTime(ledOn.at).slice(-5) : ko.captureLog.skipped}</span>
        {drift && <span style={{ color: drift === 'fail' ? 'var(--bad-ink)' : drift === 'drift' ? 'var(--warn-ink)' : undefined }}>drift {drift}</span>}
        {j.fake && <span className="text-dummy">{ko.capture.fakeFrame}</span>}
      </div>
    </li>
  )
}
