import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { NumberField } from '@/components/ui/NumberField'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { useSetup } from '../setupCtx'
import { ss } from '../strings'
import type { StepProps } from './ExposureStep'

export function ScaleStep({ cm, setCm }: StepProps) {
  const { status, run, pending, disabled, measure, setMeasure } = useSetup()
  const [potCm, setPotCm] = useState<number | ''>(status.pot_cm || 15)
  const hint = status.pts.length === 0 ? ko.setup.hint.p1 : status.pts.length === 1 ? ko.setup.hint.p2 : null
  return (
    <div className="flex flex-col gap-3">
      <NumberField label={ko.setup.lengthCm} value={cm} onChange={(v) => setCm(v === '' ? 0 : v)} min={0.5} step={0.5} unit="cm" />
      <div className="flex flex-wrap gap-2">
        <Button variant={measure ? 'primary' : 'sub'} onClick={() => setMeasure(!measure)} disabled={disabled} aria-pressed={measure} className="min-h-11 flex-1 md:min-h-0">
          {measure ? ss.measureOn : ss.measureOff}
        </Button>
        <Button variant="ghost" onClick={() => run('clearpoints')} busy={pending === 'clearpoints'} disabled={disabled} className="min-h-11 md:min-h-0">
          {ko.setup.clearPts}
        </Button>
      </div>
      {measure && hint && <div className="text-[12px] text-muted">{hint}</div>}
      {status.pts.length >= 2 && (
        <div className="num rounded-md bg-ok-soft px-3 py-2 text-[12.5px] text-ok-ink">
          {ss.scaleReadout(fmtNum(status.ppc, 1), status.cm)} — {status.msg}
        </div>
      )}
      <div className="flex items-end gap-2">
        <NumberField label={ko.setup.potCm} value={potCm} onChange={setPotCm} min={1} step={0.5} unit="cm" className="flex-1" />
        <Button variant="sub" onClick={() => potCm !== '' && run('setpot', { pot_cm: potCm })} busy={pending === 'setpot'} disabled={disabled || potCm === ''} className="h-10">
          {ko.setup.record}
        </Button>
      </div>
      <div className="text-[11.5px] text-muted">{ss.potNow(status.pot_cm)}</div>
    </div>
  )
}
