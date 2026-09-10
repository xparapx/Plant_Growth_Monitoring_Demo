import { VStepper, type Step } from '@/components/ui/Stepper'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { STEP_KEYS, useSetup } from './setupCtx'
import { CalibShotStep } from './steps/CalibShotStep'
import { ExposureStep } from './steps/ExposureStep'
import { RoiStep } from './steps/RoiStep'
import { ScaleStep } from './steps/ScaleStep'
import { TreatStep } from './steps/TreatStep'

const BODIES = [ExposureStep, ScaleStep, RoiStep, TreatStep, CalibShotStep]

export function SetupStepper({ cm, setCm }: { cm: number; setCm: (v: number) => void }) {
  const { status, activeStep } = useSetup()
  const c = status.capture
  const hints: Record<(typeof STEP_KEYS)[number], string> = {
    focus: status.done.focus ? ko.setup.stepDone.focus(fmtNum(c.exposure_us, 0, { group: false }), fmtNum(c.lens_position, 2), fmtNum(c.gain, 1)) : '',
    scale: status.done.scale ? (status.cm > 0 ? ko.setup.stepDone.scale(status.cm, fmtNum(status.ppc, 2)) : `${fmtNum(status.ppc, 2)} px/cm`) : '',
    roi: status.done.roi ? ko.setup.stepDone.roi(status.nroi) : activeStep === 2 ? ko.setup.inProgress : '',
    treat: status.done.treat ? (status.mode === 'random' ? 'random' : status.mode === 'manual' ? 'manual' : '') : activeStep === 3 ? ko.setup.inProgress : '',
    shot: status.done.shot ? ko.setup.stepDone.shot : activeStep === 4 ? ko.setup.inProgress : '',
  }
  const steps: Step[] = STEP_KEYS.map((k, i) => ({ id: k, title: ko.setup.steps[i], done: status.done[k], active: i === activeStep, hint: hints[k] }))
  return (
    <VStepper steps={steps}>
      {(_s, i) => {
        const Body = BODIES[i]
        return <Body cm={cm} setCm={setCm} />
      }}
    </VStepper>
  )
}
