import { useState } from 'react'
import { assetUrl } from '@/api/client'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { ko } from '@/i18n/ko'
import { DriftReadout } from '../DriftReadout'
import { useSetup } from '../setupCtx'
import { ss } from '../strings'
import type { StepProps } from './ExposureStep'

/** Mockup 3d step 5: one full-width #2C5979 button "5 · 기준사진 촬영 (calib.jpg)", thumbnail + drift below. */
export function CalibShotStep(_p: StepProps) {
  const { status, run, pending, disabled } = useSetup()
  const [confirm, setConfirm] = useState(false)
  const exists = status.calib.exists
  const shoot = () => { setConfirm(false); void run('shoot') }
  return (
    <div className="flex flex-col gap-3">
      <Button onClick={() => (exists ? setConfirm(true) : shoot())} busy={pending === 'shoot'} disabled={disabled} className="h-11 w-full !rounded-[10px] !text-[13px]">
        {ko.setup.shoot}
      </Button>
      {exists ? (
        <a href={assetUrl(`/api/camera/calib.jpg?t=${status.calib.mtime ?? 0}`)} target="_blank" rel="noreferrer" className="block overflow-hidden rounded-[10px] bg-sunken">
          <img src={assetUrl(`/api/camera/calib.jpg?t=${status.calib.mtime ?? 0}`)} alt={ss.calibThumb} loading="lazy" className="aspect-[16/9] w-full object-cover" />
        </a>
      ) : (
        <div className="text-[12px] text-muted">{ss.calibNone}</div>
      )}
      <DriftReadout enabled={exists && !!status.latest_raw} />
      <ConfirmDialog open={confirm} title={ko.setup.steps[4]} body={ko.setup.shootAgain} tone="accent" onCancel={() => setConfirm(false)} onConfirm={shoot} />
    </div>
  )
}
