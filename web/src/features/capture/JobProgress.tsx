import type { Job } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { Countdown } from '@/components/ui/Countdown'
import { HStepper } from '@/components/ui/Stepper'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { StatusChip } from '@/components/ui/StatusChip'
import { fmtDateTime } from '@/lib/format'
import { jobSteps, phaseLabel, stateChip, stateLabel, stepLabel } from './jobUtils'
import { cs } from './strings'

/** Screen-reader text for the current step. */
function liveText(job: Job | null): string {
  if (!job) return cs.noJob
  return cs.currentStep(stepLabel(job.step))
}

export function JobProgress({ job, last }: { job: Job | null; last: Job | null }) {
  return (
    <Card className="xl:col-span-7">
      <SectionHeader
        title={cs.progress}
        actions={job ? <StatusChip label={cs.running} state="info" detail={phaseLabel(job.phase)} /> : undefined}
      />
      <HStepper steps={jobSteps(job)} />
      <p className="sr-only" aria-live="polite">{liveText(job)}</p>
      {job?.step === 'warmup' && job.warm_until && (
        <div className="mt-3 flex items-baseline gap-2 text-[12.5px] text-muted">
          <span>{cs.warming}</span>
          <Countdown to={job.warm_until} format="s" className="text-[16px] font-bold text-ink" />
        </div>
      )}
      {!job && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[12.5px] text-muted">
          {last ? (
            <>
              <StatusChip label={stateLabel(last.state)} state={stateChip(last.state)} />
              <span className="num">{cs.lastSummary(phaseLabel(last.phase), stateLabel(last.state), fmtDateTime(last.started_at))}</span>
            </>
          ) : cs.noLast}
        </div>
      )}
    </Card>
  )
}

/** One-line variant for the camera-setup warning banner. */
export function JobProgressLine({ job }: { job: Job }) {
  const steps = jobSteps(job)
  const idx = steps.findIndex((s) => s.active)
  return (
    <span className="num text-[12px]">
      {phaseLabel(job.phase)} · {stepLabel(job.step)} ({Math.max(idx, 0) + 1}/{steps.length})
      {job.step === 'warmup' && job.warm_until && <> · <Countdown to={job.warm_until} format="s" /></>}
    </span>
  )
}
