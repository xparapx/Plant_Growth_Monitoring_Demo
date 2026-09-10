import { VStepper, type Step } from '@/components/ui/Stepper'
import { ko } from '@/i18n/ko'
import { STEP_KEYS, useSetup } from './setupCtx'
import { CalibShotStep } from './steps/CalibShotStep'
import { ExposureStep } from './steps/ExposureStep'
import { RoiStep } from './steps/RoiStep'
import { ScaleStep } from './steps/ScaleStep'
import { TreatStep } from './steps/TreatStep'

const BODIES = [ExposureStep, ScaleStep, RoiStep, TreatStep, CalibShotStep]

export function SetupStepper({ cm, setCm }: { cm: number; setCm: (v: number) => void }) {
  const { status, activeStep } = useSetup()
  const steps: Step[] = STEP_KEYS.map((k, i) => ({ id: k, title: ko.setup.steps[i], done: status.done[k], active: i === activeStep }))
  return (
    <VStepper steps={steps}>
      {(_s, i) => {
        const Body = BODIES[i]
        return <Body cm={cm} setCm={setCm} />
      }}
    </VStepper>
  )
}
