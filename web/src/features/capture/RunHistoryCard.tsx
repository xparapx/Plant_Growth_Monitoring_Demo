import { ApiError } from '@/api/client'
import { useReplayPublish } from '@/api/mutations'
import { useCaptureJobs } from '@/api/queries'
import type { Job } from '@/api/types'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { ResponsiveTable, type Col } from '@/components/ui/ResponsiveTable'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { StatusChip } from '@/components/ui/StatusChip'
import { ko } from '@/i18n/ko'
import { fmtDateTime } from '@/lib/format'
import { jobDuration, phaseLabel, stateChip, stateLabel } from './jobUtils'
import { cs } from './strings'

const COLS: Col<Job>[] = [
  { key: 'started', header: cs.started, render: (j) => fmtDateTime(j.started_at) },
  { key: 'phase', header: cs.phase, render: (j) => phaseLabel(j.phase) },
  { key: 'state', header: cs.state, render: (j) => <StatusChip label={stateLabel(j.state)} state={stateChip(j.state)} /> },
  { key: 'rows', header: 'ok/n', render: (j) => `${j.ok_rows}/${j.n_rows}`, align: 'right' },
  { key: 'trigger', header: cs.trigger, render: (j) => j.trigger },
  { key: 'dur', header: cs.duration, render: (j) => jobDuration(j), align: 'right' },
  { key: 'pub', header: cs.published, render: (j) => (j.fake ? ko.capture.fakeFrame : j.published ? ko.capture.published : ko.capture.notPublished) },
]

export function RunHistoryCard() {
  const q = useCaptureJobs(30)
  const replay = useReplayPublish()
  const err = replay.error instanceof ApiError ? `${replay.error.code}: ${replay.error.message}` : replay.error instanceof Error ? replay.error.message : null
  return (
    <Card className="md:col-span-2 xl:col-span-12">
      <SectionHeader
        title={ko.capture.history}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {replay.data && <span className="num text-[12px] text-muted">{cs.replayResult(replay.data.sent, replay.data.skipped, replay.data.errors.length)}</span>}
            {err && <span className="num text-[12px] text-bad-ink">{err}</span>}
            <Button variant="sub" size="sm" onClick={() => replay.mutate()} busy={replay.isPending}>{ko.capture.replay}</Button>
          </div>
        }
      />
      {q.isPending && <Skeleton lines={4} />}
      {q.data && (
        <ResponsiveTable
          columns={COLS}
          rows={q.data.jobs}
          rowKey={(j) => j.id}
          cardTitle={(j) => `${fmtDateTime(j.started_at)} · ${phaseLabel(j.phase)}`}
          rowTone={(j) => (j.state === 'failed' ? 'bad' : j.state === 'skipped' || j.state === 'cancelled' ? 'warn' : undefined)}
          maxHeight={420}
          empty={<EmptyState title={cs.noJobs} compact />}
        />
      )}
      {replay.data && replay.data.errors.length > 0 && (
        <ul className="num mt-2 flex flex-col gap-0.5 text-[11.5px] text-bad-ink">
          {replay.data.errors.map((e, i) => <li key={i}>{e}</li>)}
        </ul>
      )}
    </Card>
  )
}
