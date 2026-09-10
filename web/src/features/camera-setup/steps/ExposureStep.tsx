import { Button } from '@/components/ui/Button'
import { KeyValue } from '@/components/ui/KeyValue'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { useSetup } from '../setupCtx'
import { ss } from '../strings'

export interface StepProps { cm: number; setCm: (v: number) => void }

export function ExposureStep(_p: StepProps) {
  const { status, run, pending, disabled } = useSetup()
  const c = status.capture
  const busy = pending === 'auto'
  const gainTone = c.gain > 4 ? 'bad' : c.gain > 2 ? 'warn' : null
  return (
    <div className="flex flex-col gap-3">
      <Button variant="alt" size="sm" onClick={() => run('auto')} busy={busy} disabled={disabled} className="min-h-10 w-full md:min-h-9">
        {busy ? ko.setup.converging : ko.setup.auto}
      </Button>
      <KeyValue
        items={[
          { k: ss.exposure, v: fmtNum(c.exposure_us, 0) },
          { k: ss.gain, v: fmtNum(c.gain, 2) },
          { k: ss.wb, v: `${fmtNum(c.colour_gains[0], 2)} / ${fmtNum(c.colour_gains[1], 2)}` },
          { k: ss.lens, v: fmtNum(c.lens_position, 2) },
        ]}
      />
      {gainTone && (
        <div className={`rounded-md px-3 py-2 text-[12px] font-semibold ${gainTone === 'bad' ? 'bg-bad-soft text-bad-ink' : 'bg-warn-soft text-warn-ink'}`}>
          {gainTone === 'bad' ? ko.setup.gainBad : ko.setup.gainWarn}
        </div>
      )}
    </div>
  )
}
