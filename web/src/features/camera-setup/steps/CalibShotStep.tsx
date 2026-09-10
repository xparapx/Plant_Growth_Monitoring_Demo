import { useState } from 'react'
import { assetUrl } from '@/api/client'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { ko } from '@/i18n/ko'
import { DriftReadout } from '../DriftReadout'
import { useSetup } from '../setupCtx'
import { ss } from '../strings'
import type { StepProps } from './ExposureStep'

export function CalibShotStep(_p: StepProps) {
  const { status, run, pending, disabled } = useSetup()
  const [confirm, setConfirm] = useState(false)
  const exists = status.calib.exists
  const shoot = () => { setConfirm(false); void run('shoot') }
  return (
    <div className="flex flex-col gap-3">
      <Button variant="accent" onClick={() => (exists ? setConfirm(true) : shoot())} busy={pending === 'shoot'} disabled={disabled} className="min-h-11 w-full md:min-h-0 md:w-auto">
        {ko.setup.shoot}
      </Button>
      {exists ? (
        <a href={assetUrl(`/api/camera/calib.jpg?t=${status.calib.mtime ?? 0}`)} target="_blank" rel="noreferrer" className="block overflow-hidden rounded-md border border-border-soft bg-sunken">
          <img src={assetUrl(`/api/camera/calib.jpg?t=${status.calib.mtime ?? 0}`)} alt={ss.calibThumb} loading="lazy" className="aspect-[16/9] w-full object-cover" />
        </a>
      ) : (
        <div className="text-[12px] text-muted">{ss.calibNone}</div>
      )}
      <DriftReadout enabled={exists && !!status.latest_raw} />
      <ConfirmDialog open={confirm} title={ko.setup.shoot} body={ko.setup.shootAgain} tone="accent" onCancel={() => setConfirm(false)} onConfirm={shoot} />
    </div>
  )
}
