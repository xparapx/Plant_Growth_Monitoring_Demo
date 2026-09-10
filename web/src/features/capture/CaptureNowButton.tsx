import { useState } from 'react'
import { ApiError } from '@/api/client'
import { useCaptureCancel, useCaptureRun } from '@/api/mutations'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { Segmented } from '@/components/ui/Segmented'
import { Toggle } from '@/components/ui/Toggle'
import { ko } from '@/i18n/ko'
import { cs } from './strings'

type Phase = 'auto' | 'dawn' | 'pm'
const PHASES: { value: Phase; label: string }[] = [
  { value: 'auto', label: ko.capture.phase.auto },
  { value: 'dawn', label: ko.capture.phase.dawn },
  { value: 'pm', label: ko.capture.phase.pm },
]

export function CaptureNowButton({ jobRunning }: { jobRunning: boolean }) {
  const [open, setOpen] = useState(false)
  const [phase, setPhase] = useState<Phase>('auto')
  const [force, setForce] = useState(false)
  const run = useCaptureRun()
  const cancel = useCaptureCancel()
  const err = run.error instanceof ApiError ? `${run.error.code}: ${run.error.message}` : run.error instanceof Error ? run.error.message : null

  return (
    <div className="flex flex-wrap items-center gap-2">
      {jobRunning ? (
        <Button variant="ghost" onClick={() => cancel.mutate()} busy={cancel.isPending}>{cancel.isPending ? cs.cancelling : cs.cancel}</Button>
      ) : (
        <Button variant="accent" onClick={() => setOpen(true)} busy={run.isPending}>{ko.capture.now}</Button>
      )}
      {err && !jobRunning && <span className="num text-[12px] text-bad-ink" role="alert">{err}</span>}
      <ConfirmDialog
        open={open}
        title={ko.capture.confirmTitle}
        tone="accent"
        confirmLabel={ko.capture.now}
        busy={run.isPending}
        onCancel={() => setOpen(false)}
        onConfirm={() => { run.mutate({ phase, force }); setOpen(false) }}
        body={
          <div className="flex flex-col gap-3">
            <p>{ko.capture.confirmBody}</p>
            <div className="flex flex-col gap-1">
              <span className="label !text-[10px]">{cs.phaseLabel}</span>
              <Segmented options={PHASES} value={phase} onChange={setPhase} ariaLabel={cs.phaseLabel} />
            </div>
            <div className="flex items-center gap-3">
              <Toggle checked={force} onChange={setForce} label={cs.force} />
              <div>
                <div className="text-[13px] font-semibold text-ink">{cs.force}</div>
                <div className="text-[11.5px]">{cs.forceHint}</div>
              </div>
            </div>
          </div>
        }
      />
    </div>
  )
}
